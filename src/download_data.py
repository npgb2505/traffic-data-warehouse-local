from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://archive.ics.uci.edu/static/public/492/"
    "metro+interstate+traffic+volume.zip"
)
LANDING_DIR = ROOT / "data" / "landing"
RAW_PATH = ROOT / "data" / "raw" / "Metro_Interstate_Traffic_Volume.csv"
MANIFEST_PATH = ROOT / "data" / "manifests" / "metro_interstate_traffic.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str = SOURCE_URL, output: Path = RAW_PATH, force: bool = False) -> dict:
    LANDING_DIR.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and MANIFEST_PATH.exists() and not force:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        if manifest.get("output_sha256") == sha256(output):
            manifest["download_skipped"] = True
            print(json.dumps(manifest, indent=2))
            return manifest

    archive = LANDING_DIR / "metro-interstate-traffic-volume.zip"
    partial = archive.with_suffix(".zip.part")
    request = urllib.request.Request(url, headers={"User-Agent": "traffic-data-warehouse-local/2.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    partial.replace(archive)

    with zipfile.ZipFile(archive) as package:
        candidates = [name for name in package.namelist() if name.lower().endswith(".csv.gz")]
        if not candidates:
            raise RuntimeError("Downloaded UCI archive does not contain the expected CSV.GZ file")
        temporary = output.with_suffix(".csv.part")
        with package.open(candidates[0]) as compressed:
            with gzip.GzipFile(fileobj=compressed) as source, temporary.open("wb") as target:
                shutil.copyfileobj(source, target)
    temporary.replace(output)

    manifest = {
        "dataset": "Metro Interstate Traffic Volume",
        "provider": "UCI Machine Learning Repository",
        "source_url": url,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256(archive),
        "output_path": str(output),
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256(output),
        "download_skipped": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download the public UCI traffic dataset")
    parser.add_argument("--url", default=SOURCE_URL)
    parser.add_argument("--output", type=Path, default=RAW_PATH)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    download(arguments.url, arguments.output, arguments.force)
