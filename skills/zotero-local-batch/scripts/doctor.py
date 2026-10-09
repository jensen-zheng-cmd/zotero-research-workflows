"""Read-only installation diagnostics; --configure creates one local config."""
import argparse
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys
from urllib.request import Request, build_opener, ProxyHandler

import runtime_config as rc


def get_json(url, body=None):
    headers = {"Zotero-Allowed-Request": "1", "Content-Type": "application/json"}
    request = Request(url, data=None if body is None else json.dumps(body).encode(), headers=headers)
    with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
        payload = response.read()
        return {"headers": dict(response.headers), "body": json.loads(payload) if payload else {}}


def probe(config):
    checks = []

    def add(name, ok, detail, action, required=True):
        checks.append({"name": name, "ok": bool(ok), "required": required,
                       "detail": detail, "next_action": "" if ok else action})

    add("platform", platform.system() in ("Windows", "Darwin"), platform.system(),
        "Target platforms are Windows and macOS; verify other systems separately.")
    add("python", sys.version_info >= (3, 10), sys.version.split()[0], "Install Python 3.10+.")
    for name in ("pymupdf", "zotpilot"):
        try:
            version = importlib.metadata.version(name)
            available = importlib.util.find_spec(name) is not None
        except (importlib.metadata.PackageNotFoundError, ValueError, ImportError):
            version, available = None, False
        add(name, available, version, "Install the skill requirements in this interpreter.")
    directory = rc.data_dir_default(config)
    add("data_dir", directory and rc.valid_data_dir(directory), directory,
        "Resolve the running Zotero data directory; multiple candidates require confirmation.")
    try:
        api = get_json(config["api_base"] + "/api/")
        headers = {key.lower(): value for key, value in api["headers"].items()}
        add("zotero_local_api", bool(headers.get("zotero-server-id")),
            {"server_id": headers.get("zotero-server-id"), "api_version": headers.get("zotero-api-version")},
            "Use Zotero 10+ and enable local API communication.")
    except Exception as exc:
        add("zotero_local_api", False, str(exc), "Start Zotero; check API permission and local execution.")
    try:
        selected = get_json(config["api_base"] + "/connector/getSelectedCollection", {})["body"]
        ready = selected.get("libraryID") == 1 and selected.get("editable") and selected.get("filesEditable")
        add("selected_target", ready, {key: selected.get(key) for key in ("libraryID", "id", "name", "editable", "filesEditable")},
            "Select the intended editable collection in the personal library.")
    except Exception as exc:
        add("selected_target", False, str(exc), "Open Zotero and select the intended collection.")
    try:
        bridge = get_json(config["bridge_base"] + "/status")["body"]
        shape_ok = isinstance(bridge, dict) and isinstance(bridge.get("extension_connected"), bool)
        add("bridge", shape_ok, {key: bridge.get(key) for key in ("extension_connected", "extension_version", "zotero_running")} if isinstance(bridge, dict) else "Unexpected response",
            "Check whether the configured port is the ZotPilot bridge.")
        connected = shape_ok and bridge["extension_connected"]
        add("connector", connected, "heartbeat" if connected else "disconnected", "Load/reload ZotPilot Connector in the intended browser profile.")
        add("tab_reuse", connected and "+tabreuse" in str(bridge.get("extension_version", "")),
            bridge.get("extension_version"), "Inspect capabilities; apply and verify the tab-reuse patch.")
    except Exception as exc:
        add("bridge", False, str(exc), "Inspect the port, then start zotpilot bridge; do not start duplicates.")
        add("connector", False, "not_checked", "Check again after bridge is available.")
        add("tab_reuse", False, "not_checked", "Check again after bridge and Connector are available.")
    add("node", bool(shutil.which("node")), shutil.which("node"), "Install Node.js if a patch needs syntax validation.", required=False)
    return {"schema_version": 1, "python": sys.executable, "machine": platform.machine(),
            "config_path": str(rc.config_path()), "checks": checks,
            "environment_ready": all(row["ok"] for row in checks if row["required"]),
            "live_acceptance": "not_performed", "installation_complete": False}


def configure(directory=None):
    path = rc.config_path()
    if path.exists():
        raise ValueError("Configuration already exists; back it up before editing. Nothing overwritten.")
    # Explicit config path is allowed for creation, though settings() requires it to exist for use.
    if directory:
        selected = rc.require_data_dir(directory)
    else:
        candidates = rc.discover_data_dirs()
        if len(candidates) != 1:
            raise ValueError("No unique data directory; inspect candidates then use --data-dir.")
        selected = candidates[0]
    data = {"schema_version": 1, "api_base": "http://127.0.0.1:23119",
            "bridge_base": "http://127.0.0.1:2619", "data_dir": selected}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure", action="store_true")
    parser.add_argument("--data-dir", help="Confirmed data directory, used only with --configure")
    parser.add_argument("--out", help="New local diagnostic report; contains local paths")
    args = parser.parse_args()
    if args.data_dir and not args.configure:
        parser.error("--data-dir is used with --configure")
    if args.configure:
        configure(args.data_dir)
    result = probe(rc.settings())
    result["data_dir_candidates"] = rc.discover_data_dirs()
    if args.out:
        with Path(args.out).open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["environment_ready"] else 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"error": str(exc), "installation_complete": False}, ensure_ascii=False))
        raise SystemExit(1)
