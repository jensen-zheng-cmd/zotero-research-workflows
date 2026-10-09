"""Reusable local ingestion coordinator. Read-only unless run / metadata --run."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlsplit
from urllib.request import Request

import local_batch as b

FIELDS = {"abstractNote", "pages", "volume", "issue", "publicationTitle", "date",
          "ISSN", "conferenceName", "proceedingsTitle", "publisher", "place"}


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value, exclusive=True):
    with Path(path).open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)


def new_folder(path):
    folder = Path(path).resolve()
    if folder.exists() and any(folder.iterdir()):
        raise ValueError("Output folder is not empty; use a new batch folder.")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def server_id():
    request = Request(b.API + "/api/", headers={"Zotero-Allowed-Request": "1"})
    with b.OPENER.open(request, timeout=10) as response:
        value = response.headers.get("Zotero-Server-ID")
        response.read()
    if not value:
        raise RuntimeError("Zotero 10+ Server-ID required for this workflow.")
    return value


def paged(route):
    rows = []
    while True:
        page = b.http(b.API + route + f"?limit=100&start={len(rows)}")
        rows.extend(page)
        if len(page) < 100:
            return rows


def collection_path(key, by_key, seen=None):
    seen = set() if seen is None else seen
    if key in seen or key not in by_key:
        raise ValueError("Incomplete/cyclic collection tree.")
    seen.add(key)
    data = by_key[key]["data"]
    parent = data.get("parentCollection")
    return (collection_path(parent, by_key, seen) if parent else []) + [data["name"]]


def connector_collection_id(path, selected):
    """Map API key/path to Connector numeric ID through its target tree (no DB access)."""
    stack, found, personal = [], [], False
    for target in selected.get("targets", []):
        identifier = str(target.get("id", ""))
        if identifier.startswith("L"):
            personal = identifier == "L1"
            stack = []
            continue
        if not personal or not identifier.startswith("C"):
            continue
        depth = int(target.get("level", 0))
        if depth < 1 or depth > len(stack) + 1:
            raise ValueError("Connector target hierarchy cannot be mapped safely.")
        stack = stack[:depth - 1] + [target["name"]]
        if stack == path:
            found.append(int(identifier[1:]))
    if len(found) != 1:
        raise ValueError("Connector target path missing or ambiguous; inspect selected target.")
    return found[0]


def resolve_target(query):
    collections = paged("/api/users/0/collections")
    by_key = {row["key"]: row for row in collections}
    parts = [p.strip() for p in query.split("→")]
    matches = [row for row in collections if row["key"] == query or
               collection_path(row["key"], by_key) == parts or
               (len(parts) == 1 and row["data"]["name"] == parts[0])]
    if len(matches) != 1:
        raise ValueError("Target missing or ambiguous; provide a full path or collection key.")
    row = matches[0]
    path = collection_path(row["key"], by_key)
    selected = b.http(b.API + "/connector/getSelectedCollection", {})
    numeric_id = connector_collection_id(path, selected)
    return {"key": row["key"], "name": row["data"]["name"],
            "path": " → ".join(path), "id": numeric_id, "libraryID": 1}


def assert_selected(target):
    selected = b.selected_target()
    if not b.same_target(selected, target) or not selected.get("editable"):
        raise ValueError("Select the requested collection in Zotero before saving.")
    return selected


def make_plan(papers, target, items):
    rows = []
    for paper in papers:
        found = b.duplicate(paper, items)
        rows.append({"candidate": paper, "action": "reuse_existing" if found else "save",
                     "item_key": found["key"] if found else None,
                     "needs_membership": bool(found and target["key"] not in
                                              found["data"].get("collections", []))})
    return {"target": target, "plan": rows}


def membership_updates(papers, items, key):
    updates, seen = [], set()
    for paper in papers:
        found = b.duplicate(paper, items)
        if not found or found["key"] in seen:
            continue
        seen.add(found["key"])
        collections = found["data"].get("collections", [])
        if key not in collections:
            updates.append({"key": found["key"], "version": found.get("version", found["data"].get("version")),
                            "collections": [*collections, key]})
    return updates


def apply_updates(updates, expected_server, folder, prefix):
    """Single-use authorization per <=100-object request; secrets only in memory."""
    write_json(folder / (prefix + "-plan.json"), {"server_id": expected_server, "updates": updates})
    responses = []
    for offset in range(0, len(updates), 100):
        if server_id() != expected_server:
            raise RuntimeError("Zotero database changed; refuse writes.")
        headers = {"Content-Type": "application/json", "Zotero-Server-ID": expected_server,
                   "Zotero-Allowed-Request": "1"}
        emit({"action_required": "local_authorization", "app_name": "Codex Zotero Local Batch",
              "updates": min(100, len(updates) - offset)})
        request = Request(b.API + "/api/local/authorize", headers=headers,
                          data=json.dumps({"appName": "Codex Zotero Local Batch"}).encode())
        with b.OPENER.open(request, timeout=600) as response:
            authorization = json.loads(response.read())
        headers["Zotero-API-Key"] = authorization["key"]
        request = Request(b.API + "/api/users/0/items", headers=headers,
                          data=json.dumps(updates[offset:offset + 100]).encode())
        with b.OPENER.open(request, timeout=30) as response:
            result = json.loads(response.read())
        responses.append(result)
        write_json(folder / (prefix + "-result.json"), responses, exclusive=False)
        if result.get("failed"):
            raise RuntimeError("Partial write failure; inspect result and fresh object versions.")
    for patch in updates:
        current = b.http(b.API + "/api/users/0/items/" + quote(patch["key"]))["data"]
        for field, value in patch.items():
            if field not in ("key", "version") and current.get(field) != value:
                raise RuntimeError("Written fields not confirmed for " + patch["key"])
    return len(updates)


def attachment_path(data, key, directory):
    if data.get("linkMode") in ("imported_file", "imported_url"):
        filename = data.get("filename", "")
        if not filename or Path(filename).name != filename:
            return None
        return Path(directory) / "storage" / key / filename
    if data.get("linkMode") == "linked_file" and data.get("path"):
        candidate_path = Path(data["path"])
        return candidate_path if candidate_path.is_absolute() else None
    return None


def inspect_pdf(child, directory, expected):
    import pymupdf
    data = child["data"]
    path = attachment_path(data, child["key"], directory)
    result = {"key": child["key"], "source_url": data.get("url", ""),
              "path": str(path) if path else None, "readable": False,
              "identity_confirmed": False}
    try:
        if path is None:
            raise ValueError("Attachment path unresolved.")
        with pymupdf.open(path) as document:
            if not document.is_pdf or document.page_count < 1 or document.needs_pass:
                raise ValueError("Unreadable or password-protected PDF.")
            text = document[0].get_text()
            result.update(readable=True, pages=document.page_count, bytes=path.stat().st_size)
        words = set(b.title(expected["title"]).split())
        overlap = len(words & set(b.title(text).split())) / len(words) if words else None
        result["title_word_overlap"] = overlap
        result["identity_confirmed"] = bool(overlap is not None and len(words) >= 4 and overlap >= .8)
        result["doi_on_first_page"] = bool(expected["doi"] and expected["doi"] in text.lower())
        result["arxiv_version"] = re.findall(r"arXiv:\s*([^\s\[]+)", text, flags=re.I)
        if not result["identity_confirmed"]:
            result["review_required"] = "Inspect first page visually; automatic identity not confirmed."
        if result["arxiv_version"] or "arxiv.org" in result["source_url"]:
            result["edition"] = "arxiv_preprint"
        elif "proceedings.mlr.press" in result["source_url"] or "mlresearch" in result["source_url"]:
            result["edition"] = "conference_source"
        else:
            result["edition"] = "check_source_and_first_page"
    except (OSError, ValueError, RuntimeError) as exc:
        result["error"] = str(exc)
    return result


def audit(papers, target, directory):
    items = b.all_items()
    rows = []
    for paper in papers:
        found = b.duplicate(paper, items)
        row = {"candidate": paper, "status": "missing", "pdfs": []}
        if found:
            data = found["data"]
            row.update(status="present", item_key=found["key"], metadata=data,
                       in_target=target["key"] in data.get("collections", []))
            row["missing_metadata"] = [f for f in ("title", "creators", "date", "abstractNote") if not data.get(f)]
            expected = {**paper, "title": paper["title"] or data.get("title", "")}
            for child in paged("/api/users/0/items/" + quote(found["key"]) + "/children"):
                if child["data"].get("contentType") == "application/pdf":
                    row["pdfs"].append(inspect_pdf(child, directory, expected))
            row["verified_pdf"] = any(p["readable"] and p["identity_confirmed"] for p in row["pdfs"])
            if data.get("itemType") == "journalArticle" and any(p.get("edition") == "arxiv_preprint" for p in row["pdfs"]):
                row["version_notice"] = "Journal metadata with arXiv preprint PDF; not publisher typeset PDF."
        row["complete"] = bool(found and row["in_target"] and not row["missing_metadata"] and row["verified_pdf"])
        rows.append(row)
    return {"target": target, "requested": len(papers),
            "present": sum(r["status"] == "present" for r in rows),
            "verified_pdfs": sum(bool(r.get("verified_pdf")) for r in rows),
            "complete": sum(r["complete"] for r in rows), "papers": rows}


def resume_plan(manifest_path):
    manifest = read_json(manifest_path)
    if manifest["server_id"] != server_id():
        raise RuntimeError("Different Zotero database; do not resume this batch.")
    target = resolve_target(manifest["target"]["key"])
    if target["path"] != manifest["target"]["path"]:
        raise RuntimeError("Target hierarchy changed; inspect before resume.")
    save_path = Path(manifest_path).parent / "saves.json"
    previous = read_json(save_path).get("results", []) if save_path.exists() else []
    items, blockers = b.all_items(), []
    for row in previous:
        if b.duplicate(row["candidate"], items):
            continue
        if row.get("status") not in ("blocked", "failed"):
            blockers.append({"candidate": row["candidate"], "status": row.get("status"),
                             "request_id": row.get("request_id"),
                             "reason": "Not found in library; submission outcome must be resolved before resaving."})
    result = {"target": target, "blockers": blockers, "data_dir": manifest.get("data_dir"),
              "source_manifest": str(Path(manifest_path).resolve())}
    if not blockers:
        result["candidates"] = manifest["candidates"]
    return result


def metadata_updates(patches, target):
    updates, seen = [], set()
    for patch in patches:
        key = patch["item_key"]
        if key in seen:
            raise ValueError("Duplicate patch key; combine fields into one patch.")
        seen.add(key)
        source = patch.get("source_url", "")
        parsed = urlsplit(source)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Metadata patch requires a verified source URL.")
        identity = b.candidate({"url": source, **patch["identity"]})
        if not identity["doi"] and len(b.title(identity["title"])) < 40:
            raise ValueError("Metadata identity requires DOI or a full identifying title.")
        found = b.http(b.API + "/api/users/0/items/" + quote(key))
        if not b.duplicate(identity, [found]) or target["key"] not in found["data"].get("collections", []):
            raise ValueError("Metadata item identity or target membership differs.")
        fields = patch["fields"]
        if not fields or set(fields) - FIELDS or any(not isinstance(v, str) or not v.strip() for v in fields.values()):
            raise ValueError("Only supported nonempty metadata text fields may be filled.")
        update = {"key": key, "version": found.get("version", found["data"].get("version"))}
        update.update({f: v for f, v in fields.items() if not found["data"].get(f)})
        if len(update) > 2:
            updates.append(update)
    return updates


def status():
    result = {}
    for name, check in (("zotero_api", server_id), ("selected", b.selected_target),
                        ("bridge", lambda: b.http(b.BRIDGE + "/status"))):
        try:
            result[name] = {"ok": True, "value": check()}
        except Exception as exc:
            result[name] = {"ok": False, "error": str(exc)}
    ready = all(r["ok"] for r in result.values())
    if ready:
        ready = bool(result["bridge"]["value"].get("extension_connected"))
        selected = result["selected"]["value"]
        ready = ready and selected.get("libraryID") == 1 and bool(selected.get("editable"))
    result["ready_for_save"] = bool(ready)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for command in ("plan", "run", "audit", "metadata"):
        p = sub.add_parser(command)
        p.add_argument("--input", required=True)
        p.add_argument("--target", required=True)
        p.add_argument("--data-dir", default=b.runtime.data_dir_default(b.CONFIG))
        if command != "plan":
            p.add_argument("--out", required=True)
        if command == "run":
            p.add_argument("--reuse-existing", action="store_true")
        if command == "metadata":
            p.add_argument("--run", action="store_true")
    p = sub.add_parser("resume")
    p.add_argument("--from", dest="manifest", required=True)
    p.add_argument("--out", required=True)
    args = parser.parse_args()
    if args.command == "status":
        result = status()
        emit(result)
        return 0 if result["ready_for_save"] else 2
    if args.command == "resume":
        result = resume_plan(args.manifest)
        write_json(args.out, result)
        emit(result)
        return 2 if result["blockers"] else 0
    if args.command in ("run", "audit"):
        args.data_dir = b.runtime.require_data_dir(args.data_dir)
        # Fail before any save if the PDF verifier is unavailable.
        import pymupdf
    target = resolve_target(args.target)
    if args.command == "metadata":
        patches = read_json(args.input)
        updates = metadata_updates(patches, target)
        folder = new_folder(args.out)
        write_json(folder / "metadata-sources.json", patches)
        if args.run:
            changed = apply_updates(updates, server_id(), folder, "metadata")
            emit({"updated": changed, "target": target})
        else:
            result = {"target": target, "updates": updates, "mode": "plan_only"}
            write_json(folder / "metadata-plan.json", result)
            emit(result)
        return 0
    papers = b.load_candidates(args.input)
    if args.command == "plan":
        emit(make_plan(papers, target, b.all_items()))
        return 0
    if args.command == "audit":
        result = audit(papers, target, args.data_dir)
        write_json(args.out, result)
        emit({k: v for k, v in result.items() if k != "papers"})
        return 0 if result["complete"] == result["requested"] else 2
    ready = b.health()
    assert_selected(target)
    if args.reuse_existing and "+tabreuse" not in ready["bridge"].get("extension_version", ""):
        raise ValueError("Verified-tab reuse patch not loaded; inspect Connector before retrying.")
    folder = new_folder(args.out)
    instance = server_id()
    # Manifest before the first save enables recovery even when the coordinator is interrupted.
    write_json(folder / "manifest.json", {"server_id": instance, "target": target,
               "candidates": papers, "data_dir": str(Path(args.data_dir).resolve())})
    saves = b.run_batch(papers, target["name"], folder / "saves.json", args.data_dir, args.reuse_existing)
    if server_id() != instance:
        raise RuntimeError("Database changed during saves; inspect report before further changes.")
    assert_selected(target)
    updates = membership_updates(papers, b.all_items(), target["key"])
    changed = apply_updates(updates, instance, folder, "membership")
    result = audit(papers, target, args.data_dir)
    write_json(folder / "audit.json", result)
    counts = dict(Counter(r["status"] for r in saves["results"]))
    report = {"target": target, "save_status_counts": counts, "memberships_added": changed,
              "requested": len(papers), "verified_pdfs": result["verified_pdfs"],
              "complete": result["complete"], "remaining": saves["remaining"],
              "audit": str(folder / "audit.json")}
    write_json(folder / "report.json", report)
    emit(report)
    return 0 if result["complete"] == len(papers) else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except Exception as exc:
        emit({"error": str(exc), "action_required": "inspect_report_and_local_state"})
        raise SystemExit(1)
