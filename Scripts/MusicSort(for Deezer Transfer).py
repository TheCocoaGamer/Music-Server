import os, shutil, hashlib
from pathlib import Path

# Load .env
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env()

# ========= CONFIG =========
SOURCE_ROOT = Path(os.environ['SOURCE_ROOT'])
DEST_ROOT   = Path(os.environ['DEST_ROOT'])
ALL_SONGS   = DEST_ROOT / "AllSongs"
PLAYLISTS   = DEST_ROOT / "Playlists"

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".wma", ".aiff", ".alac"}

WRITE_EXTM3U      = True
NORMALIZE_SLASHES = True
# ==========================

def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS

def sha1_file(path: Path, bufsize: int = 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            h.update(chunk)
    return h.hexdigest()

def unique_dest_path(base_dir: Path, filename: str) -> Path:
    stem = Path(filename).stem
    ext  = Path(filename).suffix
    candidate = base_dir / f"{stem}{ext}"
    i = 2
    while candidate.exists():
        candidate = base_dir / f"{stem} ({i}){ext}"
        i += 1
    return candidate

def update_playlist(pl_name: str, song_rel: str):
    """Append song_rel into Playlists/pl_name.m3u if not already there."""
    PLAYLISTS.mkdir(parents=True, exist_ok=True)
    pl_path = PLAYLISTS / f"{pl_name}.m3u"

    lines = []
    if pl_path.exists():
        lines = pl_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Ensure header
    if WRITE_EXTM3U:
        if not lines:
            lines.append("#EXTM3U")
        elif lines[0] != "#EXTM3U":
            lines.insert(0, "#EXTM3U")

    if song_rel in lines:
        print(f"🔁 Already in {pl_name}")
        return

    with pl_path.open("w", encoding="utf-8", newline="\n") as f:
        for line in lines:
            f.write(line + "\n")
        f.write(song_rel + "\n")

    print(f"✅ Added to {pl_name}")

def main():
    if not SOURCE_ROOT.exists():
        print(f"ERROR: SOURCE_ROOT not found: {SOURCE_ROOT}")
        return

    ALL_SONGS.mkdir(parents=True, exist_ok=True)
    PLAYLISTS.mkdir(parents=True, exist_ok=True)

    to_process = []
    for root, dirs, files in os.walk(SOURCE_ROOT):
        root_path = Path(root)
        rel_to_source = root_path.relative_to(SOURCE_ROOT)
        if rel_to_source == Path('.'):
            continue  # skip root-level files, only process subfolders

        playlist_name = rel_to_source.parts[0]

        for fname in files:
            p = root_path / fname
            if is_audio(p):
                to_process.append((p, playlist_name))

    if not to_process:
        print("No new audio files found in Raw Songs.")
        return

    print(f"Found {len(to_process)} audio file(s).")

    for src, playlist_name in to_process:
        print(f"\nProcessing: {src.relative_to(SOURCE_ROOT)}")

        try:
            _ = sha1_file(src)
        except Exception as e:
            print(f" ! Skipping unreadable file: {src} ({e})")
            continue

        dest = unique_dest_path(ALL_SONGS, src.name)
        shutil.move(str(src), str(dest))
        print(f"   ➡️ Moved to {dest}")

        rel = os.path.relpath(dest, PLAYLISTS)
        if NORMALIZE_SLASHES:
            rel = rel.replace("\\", "/")

        update_playlist(playlist_name, rel)

    print("\nDone.")

if __name__ == "__main__":
    main()
