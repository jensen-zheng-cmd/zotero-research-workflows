"""Portable, local-only settings. No writes or imports from ZotPilot."""
import configparser
import json
import os
from pathlib import Path
import platform
import re
from urllib.parse import urlsplit

SKILL_ROOT = Path(__file__).resolve().parent.parent


def config_path():
    value = os.environ.get("ZOTERO_BATCH_CONFIG")
    if value:
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("ZOTERO_BATCH_CONFIG must be an absolute path.")
        return path
    return SKILL_ROOT / "runtime.local.json"


def local_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or not parsed.port):
        raise ValueError("Endpoint must be a loopback HTTP origin with an explicit port.")
    return value.rstrip("/")


def settings():
    result = {"schema_version": 1, "api_base": "http://127.0.0.1:23119",
              "bridge_base": "http://127.0.0.1:2619", "data_dir": None}
    path = config_path()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or set(data) - set(result):
            raise ValueError("Unknown runtime.local.json fields; use the documented schema.")
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported runtime configuration schema.")
        result.update(data)
    elif os.environ.get("ZOTERO_BATCH_CONFIG"):
        raise ValueError("Explicit ZOTERO_BATCH_CONFIG does not exist.")
    for key in ("api_base", "bridge_base"):
        result[key] = local_url(result[key])
    if result["data_dir"] is not None:
        value = Path(result["data_dir"]).expanduser()
        if not value.is_absolute():
            raise ValueError("data_dir must be an absolute path.")
        result["data_dir"] = str(value)
    return result


def valid_data_dir(path):
    return Path(path).is_dir() and (Path(path) / "zotero.sqlite").is_file()


def discover_data_dirs(home=None, system=None, environ=None):
    """Collect candidates, never silently pick the first of several profiles."""
    home = Path(home) if home is not None else Path.home()
    system = system or platform.system()
    environ = os.environ if environ is None else environ
    roots = {
        "Windows": [Path(environ.get("APPDATA", str(home / "AppData/Roaming"))) / "Zotero/Zotero"],
        "Darwin": [home / "Library/Application Support/Zotero"],
        "Linux": [home / ".zotero/zotero"],
    }.get(system, [])
    candidates = [home / "Zotero"]
    for root in roots:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(root / "profiles.ini", encoding="utf-8-sig")
        except (OSError, configparser.Error):
            continue
        for section in parser.sections():
            if not section.startswith("Profile") or not parser.has_option(section, "Path"):
                continue
            profile = Path(parser.get(section, "Path"))
            if parser.get(section, "IsRelative", fallback="1") == "1":
                profile = root / profile
            candidates.append(profile / "zotero")
            try:
                text = (profile / "prefs.js").read_text(encoding="utf-8-sig")
            except OSError:
                continue
            if not re.search(r'user_pref\("extensions\.zotero\.useDataDir",\s*true\s*\)', text):
                continue
            match = re.search(r'user_pref\("extensions\.zotero\.dataDir",\s*("(?:\\.|[^"\\])*")\s*\)', text)
            if match:
                try:
                    custom = Path(json.loads(match[1])).expanduser()
                    if custom.is_absolute():
                        candidates.append(custom)
                except (ValueError, TypeError):
                    pass
    return sorted({str(path.resolve()) for path in candidates if valid_data_dir(path)})


def data_dir_default(config=None):
    config = settings() if config is None else config
    if config["data_dir"]:
        return config["data_dir"]
    paths = discover_data_dirs()
    return paths[0] if len(paths) == 1 else None


def require_data_dir(value):
    path = Path(value).expanduser() if value else None
    if path is None or not valid_data_dir(path):
        raise ValueError("Zotero data directory unresolved; run doctor.py or pass --data-dir.")
    return str(path.resolve())
