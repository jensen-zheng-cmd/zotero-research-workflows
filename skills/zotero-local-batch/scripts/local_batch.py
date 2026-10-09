"""Batch-save through the real browser Connector; no Zotero cloud credentials.

Default is a read-only plan. --run requires an explicit selected target and a new
report file. Report uncertain submissions before stopping; never auto-retry saves.
"""
import argparse
import json
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, build_opener, ProxyHandler
import runtime_config as runtime

CONFIG = runtime.settings()
API = CONFIG["api_base"]
BRIDGE = CONFIG["bridge_base"]
OPENER = build_opener(ProxyHandler({}))


def http(url, body=None):
    headers = {"Accept": "application/json", "Zotero-Allowed-Request": "1"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
    with OPENER.open(req, timeout=10) as response:
        content = response.read()
        return json.loads(content) if content else None


def doi(value):
    value = unquote(str(value or "").strip())
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.I)
    return value.lower() if re.fullmatch(r"10\.\d{4,9}/\S+", value) else ""


def title(value):
    return " ".join(re.findall(r"\w+", str(value or "").lower()))


def url_identity(value):
    parsed = urlsplit(str(value or ""))
    if parsed.hostname in ("arxiv.org", "www.arxiv.org"):
        match = re.search(r"/(?:abs|pdf)/(.+?)(?:\.pdf)?$", parsed.path)
        if match:
            return "arxiv:" + re.sub(r"v\d+$", "", match[1]).lower()
    return str(value or "").rstrip("/")


def candidate(raw):
    data = {"url": raw} if isinstance(raw, str) else dict(raw)
    d = doi(data.get("doi") or data.get("url"))
    link = data.get("landing_page_url") or data.get("url")
    if not link and d:
        link = "https://doi.org/" + d
    if not link and data.get("arxiv_id"):
        link = "https://arxiv.org/abs/" + data["arxiv_id"]
    if doi(link):
        link = "https://doi.org/" + doi(link)
    if not isinstance(link, str) or urlsplit(link).scheme not in ("http", "https"):
        raise ValueError("Each entry needs a DOI or HTTP(S) paper URL; resolve titles first.")
    return {"url": link, "doi": d, "title": data.get("title", "")}


def load_candidates(path):
    content = Path(path).read_text(encoding="utf-8-sig")
    if Path(path).suffix.lower() == ".json":
        rows = json.loads(content)
        if isinstance(rows, dict):
            rows = rows.get("candidates", rows.get("results"))
    else:
        rows = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected a nonempty candidate list.")
    return [candidate(row) for row in rows]


def all_items():
    items = []
    while True:
        page = http(API + f"/api/users/0/items/top?limit=100&start={len(items)}&format=json")
        items.extend(page)
        if len(page) < 100:
            return items


def duplicate(paper, items):
    for item in items:
        data = item["data"]
        if data.get("itemType") in ("attachment", "note"):
            continue
        if paper["doi"] and paper["doi"] == doi(data.get("DOI")):
            return item
        # A known, different DOI can identify a distinct publication version.
        # Do not silently substitute an arXiv preprint for a requested journal DOI.
        if paper["doi"] and doi(data.get("DOI")) and paper["doi"] != doi(data["DOI"]):
            continue
        if data.get("url") and url_identity(paper["url"]) == url_identity(data["url"]):
            return item
        normalized = title(paper["title"])
        if len(normalized) >= 40 and normalized == title(data.get("title")):
            return item
    return None


def selected_target():
    selected = http(API + "/connector/getSelectedCollection", {})
    return {field: selected.get(field) for field in ("libraryID", "libraryName", "id", "name", "editable", "filesEditable")}


def health():
    bridge = http(BRIDGE + "/status")
    if not bridge.get("extension_connected"):
        raise RuntimeError("Connector offline: keep the browser and ZotPilot Connector enabled.")
    http(API + "/api/users/0/collections?limit=1")
    target = selected_target()
    if target.get("libraryID") != 1:
        raise RuntimeError("This local batch entry currently supports the personal library only.")
    if not target.get("editable"):
        raise RuntimeError("Selected library is not editable.")
    return {"bridge": bridge, "target": target}


def same_target(a, b):
    return a["libraryID"] == b["libraryID"] and a["id"] == b["id"]


def verify(paper, result, before, after, data_dir):
    previous = {item["key"] for item in before}
    new = [item for item in after if item["key"] not in previous and item["data"].get("itemType") not in ("note", "attachment")]
    matching = duplicate(paper, new)
    reported = next((item for item in new if item["key"] == result.get("item_key")), None)
    # Known identifiers take precedence over the extension's sometimes ambiguous key.
    found = matching if paper["doi"] or paper["title"] else (matching or reported)
    if not found:
        return {"status": "unconfirmed", "has_pdf": False, "new_item_keys": [i["key"] for i in new]}
    children = http(API + "/api/users/0/items/" + quote(found["key"]) + "/children?limit=100")
    pdf_keys = []
    for child in children:
        data = child["data"]
        if data.get("itemType") != "attachment" or data.get("contentType") != "application/pdf":
            continue
        if data.get("linkMode") in ("imported_file", "imported_url") and data_dir:
            path = Path(data_dir) / "storage" / child["key"] / data.get("filename", "")
        elif data.get("linkMode") == "linked_file" and data.get("path"):
            path = Path(data["path"])
        else:
            continue
        try:
            with path.open("rb") as attachment:
                if attachment.read(5) == b"%PDF-":
                    pdf_keys.append(child["key"])
        except OSError:
            pass
    data = found["data"]
    return {"status": "saved_with_pdf" if pdf_keys else "saved_metadata_only", "has_pdf": bool(pdf_keys),
            "item_key": found["key"], "title": data.get("title"), "pdf_keys": pdf_keys,
            "metadata_fields": sorted(k for k, v in data.items() if v), "collections": data.get("collections", [])}


def persist(report, path):
    Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def run_batch(papers, target_name, report_path, data_dir, reuse_existing=False):
    if Path(report_path).exists():
        raise ValueError("Report already exists; inspect it before retrying any previous saves.")
    ready = health()
    target = ready["target"]
    if target_name != (target["name"] or target["libraryName"]):
        raise ValueError("Select the specified collection in Zotero before running.")
    report = {"target": target, "results": [], "mode": "local_connector_no_cloud"}
    items = all_items()
    persist(report, report_path)
    for paper in papers:
        row = {"candidate": paper}
        report["results"].append(row)
        try:
            existing = duplicate(paper, items)
            if existing:
                row.update(status="duplicate", item_key=existing["key"], title=existing["data"].get("title"))
            else:
                if not same_target(target, selected_target()):
                    raise RuntimeError("Selected collection changed; batch stopped.")
                row["status"] = "submitting"
                persist(report, report_path)
                command = {"action": "save", "url": paper["url"]}
                if reuse_existing:
                    command["reuse_existing"] = True
                response = http(BRIDGE + "/enqueue", command)
                row.update(status="pending", request_id=response["request_id"])
                persist(report, report_path)
                deadline = time.monotonic() + 220
                result = None
                while time.monotonic() < deadline:
                    result = http(BRIDGE + "/result/" + quote(row["request_id"]))
                    if result:
                        break
                    time.sleep(1)
                row["connector_result"] = result
                if result is None:
                    row.update(status="unconfirmed", error="Timeout; inspect Zotero before retrying.")
                elif result.get("error_code") == "anti_bot_detected":
                    row.update(status="blocked", error="Complete verification in the browser tab left open.")
                else:
                    after = all_items()
                    row.update(verify(paper, result, items, after, data_dir))
                    items = after
                    if row["status"] == "unconfirmed" and result.get("success") is False and not row.get("new_item_keys"):
                        row.update(status="failed", error=result.get("error_message") or result.get("error_code"))
                if not same_target(target, selected_target()):
                    row["target_warning"] = "Selected collection changed during save; inspect this item's collection."
        except Exception as exc:
            row.update(status="unconfirmed" if row.get("status") in ("submitting", "pending") else "failed", error=str(exc))
            row["stop_batch"] = True
        persist(report, report_path)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        if row["status"] in ("unconfirmed", "blocked") or row.get("stop_batch") or row.get("target_warning"):
            break
    report["remaining"] = papers[len(report["results"]):]
    persist(report, report_path)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="JSON candidates, or one DOI / URL per line")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--run", action="store_true", help="Actually save papers (default: plan only)")
    parser.add_argument("--target", help="Exact name of currently selected Zotero collection")
    parser.add_argument("--report", help="New JSON report path; required with --run")
    parser.add_argument("--data-dir", default=runtime.data_dir_default(CONFIG))
    parser.add_argument("--reuse-existing", action="store_true", help="Prefer an already verified paper tab; requires locally patched Connector")
    args = parser.parse_args()
    if args.status:
        print(json.dumps(health(), ensure_ascii=False, indent=2))
        return
    if not args.input:
        parser.error("--input is required")
    papers = load_candidates(args.input)
    if args.run:
        if not args.target or not args.report:
            parser.error("--run requires --target and --report")
        args.data_dir = runtime.require_data_dir(args.data_dir)
        report = run_batch(papers, args.target, args.report, args.data_dir, args.reuse_existing)
        if report["remaining"] or any(r["status"] in ("failed", "blocked", "unconfirmed") or r.get("target_warning") for r in report["results"]):
            raise SystemExit(2)
    else:
        items = all_items()
        print(json.dumps({"target": health()["target"], "plan": [{"candidate": p, "action": "skip_duplicate" if duplicate(p, items) else "save"} for p in papers]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        raise SystemExit(1)
