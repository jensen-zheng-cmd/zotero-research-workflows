"""Download, verify and prepare a Connector copy. Does not load it into a browser."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def validate_archive(payload, expected_hash):
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise ValueError("Connector SHA256 mismatch; no files extracted.")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for item in archive.infolist():
            name = item.filename.replace("\\", "/")
            parts = name.split("/")
            if name.startswith("/") or ".." in parts or ":" in name:
                raise ValueError("Unsafe archive path.")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive symlinks are not supported.")
        bad = archive.testzip()
        if bad:
            raise ValueError("Corrupt archive member: " + bad)


def prepare(output, archive_path=None):
    release = json.loads((ROOT / "references/connector-release.json").read_text(encoding="utf-8"))
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("Output already exists; reuse the previous prepared copy or choose a new directory.")
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js is required to check the patched extension syntax.")
    if archive_path:
        payload = Path(archive_path).read_bytes()
    else:
        request = urllib.request.Request(release["asset_url"], headers={"User-Agent": "zotero-research-workflows"})
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = response.read()
    validate_archive(payload, release["sha256"])
    output.mkdir(parents=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(output)
    extension = output / release["extension_directory"]
    source = extension / release["script"]
    manifest = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))
    if not source.is_file() or not manifest.get("manifest_version"):
        raise ValueError("Expected extension files missing.")
    patched = source.with_name("agentAPI.patched.js")
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/patch_connector.py"),
                    "--source", str(source), "--out", str(patched)], check=True)
    subprocess.run([node, "--check", str(patched)], check=True)
    backup = source.with_name("agentAPI.before-tab-reuse.js.bak")
    shutil.copy2(source, backup)
    patched.replace(source)
    report = {"release": release["version"], "asset_url": release["asset_url"],
              "sha256": release["sha256"], "extension_directory": str(extension),
              "manifest_version": manifest.get("version"), "backup": str(backup),
              "prepared": True, "browser_loaded": False, "live_verified": False}
    (output / "prepared.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New, stable, local directory, never committed")
    parser.add_argument("--archive", help="Existing official release ZIP, still SHA256 checked")
    args = parser.parse_args()
    print(json.dumps(prepare(args.out, args.archive), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
