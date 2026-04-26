"""Orquestador del pipeline.

Pasos:
  1. Lee data/index.json (videos ya procesados).
  2. Obtiene la lista actual de favoritos/likes desde TikTok
     (scripts/fetch_favorites.py) — opcionalmente, acepta URLs sueltas
     pasadas por la variable MANUAL_URLS (separadas por coma) para el
     flujo "compartir desde Android".
  3. Para cada video nuevo:
        - descarga .mp4 con yt-dlp
        - transcribe con faster-whisper -> .txt + .json
        - escribe metadata.json
        - sube a Drive con rclone
  4. Actualiza data/index.json y deja todo listo para commit.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = ROOT / "data" / "index.json"
WORK = ROOT / "work"
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, check=True, **kwargs)


def load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text() or "{}")
    return {}


def save_index(idx: dict) -> None:
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(json.dumps(idx, ensure_ascii=False, indent=2, sort_keys=True))


def fetch_from_tiktok() -> list[dict]:
    out = subprocess.run(
        [sys.executable, str(SCRIPTS / "fetch_favorites.py")],
        check=True,
        capture_output=True,
        text=True,
        env=os.environ,
    )
    return json.loads(out.stdout or "[]")


def fetch_from_manual_urls() -> list[dict]:
    raw = os.environ.get("MANUAL_URLS", "").strip()
    if not raw:
        return []
    items = []
    for url in [u.strip() for u in raw.split(",") if u.strip()]:
        # Acepta URLs cortas y largas; yt-dlp resolverá metadata.
        items.append({"id": url.rsplit("/", 1)[-1].split("?")[0], "url": url, "author": "", "desc": "", "create_time": None, "duration": None})
    return items


def yt_dlp_download(url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_tpl = str(dest_dir / "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-warnings",
        "--restrict-filenames",
        "-f", "mp4/best",
        "-o", out_tpl,
        "--print", "after_move:filepath",
        url,
    ]
    cookies = os.environ.get("TIKTOK_COOKIES")
    if cookies:
        cookie_file = Path("/tmp/yt_cookies.txt")
        cookie_file.write_text(cookies)
        cmd[1:1] = ["--cookies", str(cookie_file)]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    path = out.stdout.strip().splitlines()[-1]
    return Path(path)


def transcribe(video: Path, txt_out: Path, json_out: Path) -> None:
    run([
        sys.executable, str(SCRIPTS / "transcribe.py"),
        str(video), str(txt_out), "--json", str(json_out),
    ])


def rclone_upload(local_dir: Path, remote_subdir: str) -> None:
    remote = os.environ.get("RCLONE_REMOTE", "drive")
    base = os.environ.get("RCLONE_BASE_DIR", "TikTok-Favoritos")
    target = f"{remote}:{base}/{remote_subdir}"
    run(["rclone", "copy", str(local_dir), target, "--transfers=2", "--checkers=4"])


def process(item: dict, idx: dict) -> bool:
    vid = item["id"]
    if vid in idx:
        return False
    print(f"[sync] nuevo video {vid} ({item.get('author','?')})", file=sys.stderr)

    work_dir = WORK / vid
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    try:
        video_path = yt_dlp_download(item["url"], work_dir)
    except subprocess.CalledProcessError as e:
        print(f"[sync] error yt-dlp en {vid}: {e.stderr or e}", file=sys.stderr)
        return False

    txt_path = work_dir / f"{vid}.txt"
    json_path = work_dir / f"{vid}.json"
    try:
        transcribe(video_path, txt_path, json_path)
    except subprocess.CalledProcessError as e:
        print(f"[sync] error transcripción en {vid}: {e}", file=sys.stderr)
        return False

    metadata = {
        **item,
        "video_file": video_path.name,
        "txt_file": txt_path.name,
        "json_file": json_path.name,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    (work_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2)
    )

    if os.environ.get("RCLONE_UPLOAD", "1") == "1":
        ts = datetime.now(timezone.utc).strftime("%Y-%m")
        try:
            rclone_upload(work_dir, ts)
        except subprocess.CalledProcessError as e:
            print(f"[sync] error rclone en {vid}: {e}", file=sys.stderr)
            return False

    idx[vid] = {
        "url": item["url"],
        "author": item.get("author", ""),
        "desc": item.get("desc", ""),
        "processed_at": metadata["processed_at"],
    }

    if os.environ.get("KEEP_LOCAL", "0") != "1":
        shutil.rmtree(work_dir, ignore_errors=True)
    return True


def main() -> int:
    WORK.mkdir(exist_ok=True)
    idx = load_index()

    items = fetch_from_manual_urls() or fetch_from_tiktok()
    print(f"[sync] {len(items)} videos en la fuente, {len(idx)} ya procesados", file=sys.stderr)

    new_count = 0
    for item in items:
        if process(item, idx):
            new_count += 1
            save_index(idx)  # guarda incremental por si falla a mitad

    print(f"[sync] añadidos {new_count} nuevos", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
