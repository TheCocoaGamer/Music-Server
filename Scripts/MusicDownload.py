import asyncio
import aiofiles
import os
import shutil
from yt_dlp import YoutubeDL
from mutagen.id3 import ID3, COMM, APIC, TPE1, ID3NoHeaderError

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

# ------------------------
# Config
# ------------------------
SONGS_FILE = os.environ['SONGS_FILE']
TEMP_DIR = os.environ['TEMP_DIR']
PLAYLISTS_DIR = os.environ['PLAYLISTS_DIR']
ALL_SONGS = os.environ['ALL_SONGS']
MAX_CONCURRENT = 10

# ------------------------
# Helpers
# ------------------------
async def async_input(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

def run_download(ydl_opts, url):
    """Run yt-dlp synchronously (executed inside an executor). Return the info dict."""
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info

def download_thumbnail(url):
    """Download thumbnail image data and mime type from URL."""
    import urllib.request
    with urllib.request.urlopen(url) as response:
        data = response.read()
        mime = response.headers.get('content-type', 'image/jpeg')
        return data, mime

def find_downloaded_file_from_info(info):
    """Try to locate the final file in TEMP_DIR using info dict returned by yt-dlp."""
    title = info.get("title") or ""
    try:
        candidates = []
        for fname in os.listdir(TEMP_DIR):
            if title and title.lower() in fname.lower():
                candidates.append(os.path.join(TEMP_DIR, fname))
        if candidates:
            return max(candidates, key=os.path.getmtime)
    except FileNotFoundError:
        pass

    ext = info.get("ext")
    if title and ext:
        candidate = os.path.join(TEMP_DIR, f"{title}.{ext}")
        if os.path.exists(candidate):
            return candidate

    return None

def tag_song_with_playlists(song_path: str, playlists: list[str], thumbnail_data=None, mime=None, uploader=None):
    """
    Writes all playlist names into the comment field of the MP3, embeds thumbnail, and sets artist.
    """
    comment_text = ", ".join(playlists)

    try:
        tags = ID3(song_path)
    except ID3NoHeaderError:
        tags = ID3()  # create new ID3 tag block if missing

    tags.delall("COMM")  # remove old comments
    tags.add(COMM(encoding=3, lang="eng", desc="", text=comment_text))

    if thumbnail_data:
        tags.add(APIC(encoding=3, mime=mime or 'image/jpeg', type=3, desc='Cover', data=thumbnail_data))

    if uploader:
        tags.add(TPE1(encoding=3, text=uploader))

    # Save in ID3v2.3 (most compatible with Explorer/Foobar)
    tags.save(song_path, v2_version=3)

    print(f"✅ {os.path.basename(song_path)} → {comment_text}")

# ------------------------
# Core: download -> (maybe move) -> update playlists -> remove from songs.txt
# ------------------------
async def download_song(entry, playlist_names):
    url = entry["url"]
    original_input = entry.get("input", url)
    print(f"🔹 Starting download: {url}", flush=True)

    ydl_opts = {
        "outtmpl": os.path.join(TEMP_DIR, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
        }],
    }

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, run_download, ydl_opts, url)
    except Exception as e:
        print(f"⚠️ Download failed for {url}: {e}", flush=True)
        return

    # Download thumbnail
    thumbnail_data = None
    mime = None
    if thumbnail_url := info.get('thumbnail'):
        try:
            thumbnail_data, mime = await asyncio.to_thread(download_thumbnail, thumbnail_url)
        except Exception as e:
            print(f"⚠️ Failed to download thumbnail: {e}", flush=True)

    uploader = info.get('uploader')

    src = find_downloaded_file_from_info(info)
    if not src:
        print("⚠️ Could not locate downloaded file in TempDownloads.", flush=True)
        return

    dst = src  # default: stays in TempDownloads

    if playlist_names:  # move into AllSongs if playlists were chosen
        os.makedirs(ALL_SONGS, exist_ok=True)

        base = os.path.basename(src)
        name_no_ext, ext = os.path.splitext(base)
        dst = os.path.join(ALL_SONGS, base)
        i = 2
        while os.path.exists(dst):
            dst = os.path.join(ALL_SONGS, f"{name_no_ext} ({i}){ext}")
            i += 1

        try:
            await asyncio.to_thread(shutil.move, src, dst)
            print(f"➡️  Moved {os.path.basename(dst)} into AllSongs", flush=True)
        except Exception as e:
            print(f"⚠️ Error moving file into AllSongs: {e}", flush=True)
            return

        # Add to *each* chosen playlist
        for pl in playlist_names:
            pl_path = os.path.join(PLAYLISTS_DIR, f"{pl}.m3u")
            rel = os.path.relpath(dst, PLAYLISTS_DIR).replace("\\", "/")

            try:
                if not os.path.exists(pl_path):
                    async with aiofiles.open(pl_path, "w", encoding="utf-8") as f:
                        await f.write("#EXTM3U\n")
                # Append the entry
                async with aiofiles.open(pl_path, "a", encoding="utf-8") as f:
                    await f.write('\n' + rel)
                print(f"🎵 Added {os.path.basename(dst)} to {pl}.m3u", flush=True)
            except Exception as e:
                print(f"⚠️ Error adding to playlist {pl}: {e}", flush=True)

        # Tag MP3 with playlist information
        tag_song_with_playlists(dst, playlist_names, thumbnail_data, mime, uploader)

    # Tag MP3 even if no playlists selected (for TempDownloads)
    if not playlist_names:
        tag_song_with_playlists(dst, [], thumbnail_data, mime, uploader)

    await remove_from_txt(original_input)
    print(f"✅ Finished download and processing: {os.path.basename(dst)}", flush=True)

# ------------------------
# Remove song/query from songs.txt
# ------------------------
async def remove_from_txt(original_line):
    if not os.path.exists(SONGS_FILE):
        return
    try:
        async with aiofiles.open(SONGS_FILE, "r", encoding="utf-8") as f:
            lines = await f.readlines()
    except Exception:
        lines = []

    target = (original_line or "").strip()
    async with aiofiles.open(SONGS_FILE, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip() and line.strip() != target:
                await f.write(line)

# ------------------------
# Playlist selection (multi-choice)
# ------------------------
async def choose_playlists():
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)
    playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
    print("\nAvailable playlists:")
    cols = 3
    for i, name in enumerate(playlists, 1):
        display_name = name[:27] + '...' if len(name) > 30 else name
        print(f"{i:2}. {display_name:<30}", end=" ")
        if i % cols == 0:
            print()
    print(f"{len(playlists)+1:2}. + Create new playlist\n")

    choice = (await async_input("Choose playlist numbers (comma/space separated, 0=skip): ")).strip()
    if not choice or choice == "0":
        return []

    indices = [int(x) for x in choice.replace(",", " ").split() if x.isdigit()]
    chosen = []
    for idx in indices:
        if idx == len(playlists) + 1:
            new_name = (await async_input("Enter new playlist name: ")).strip()
            if new_name:
                pl_file = os.path.join(PLAYLISTS_DIR, f"{new_name}.m3u")
                if not os.path.exists(pl_file):
                    async with aiofiles.open(pl_file, "w", encoding="utf-8") as f:
                        await f.write("#EXTM3U\n")
                chosen.append(new_name)
        elif 1 <= idx <= len(playlists):
            chosen.append(playlists[idx - 1])
    return chosen

# ------------------------
# Search helper
# ------------------------
def get_title_from_url(url):
    """Get title from URL using yt-dlp without downloading."""
    opts = {"quiet": True, "skip_download": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("title", url)

def search_youtube_sync(query, max_results=5):
    opts = {"quiet": True, "skip_download": True, "extract_flat": "in_playlist"}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        return info.get("entries", [])

async def search_youtube(query, max_results=5):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, search_youtube_sync, query, max_results)

# ------------------------
# Orchestrator
# ------------------------
sem = asyncio.Semaphore(MAX_CONCURRENT)
async def limit_downloads(entry, playlist_names):
    async with sem:
        await download_song(entry, playlist_names)

async def process_links():
    try:
        async with aiofiles.open(SONGS_FILE, "r", encoding="utf-8") as f:
            lines = await f.readlines()
    except UnicodeDecodeError:
        async with aiofiles.open(SONGS_FILE, "r", encoding="cp1252") as f:
            lines = await f.readlines()
    except FileNotFoundError:
        print("No songs.txt found; nothing to do.", flush=True)
        return

    links = [l.strip() for l in lines if "http" in l]
    queries = [l.strip() for l in lines if "http" not in l and l.strip()]

    tasks = []
    for url in links:
        title = await asyncio.to_thread(get_title_from_url, url)
        print(f"\nProcessing: \x1b]8;;{url}\x1b\\{title}\x1b]8;;\x1b\\", flush=True)
        playlist_names = await choose_playlists()
        entry = {"url": url, "input": url}
        tasks.append(asyncio.create_task(limit_downloads(entry, playlist_names)))

    for query in queries:
        results = await search_youtube(query, max_results=5)
        if not results:
            print(f"\nNo results for: {query}", flush=True)
            continue

        print(f"\nResults for: {query}", flush=True)
        for i, r in enumerate(results, 1):
            title = r.get("title", "Unknown")
            uploader = r.get("uploader", "Unknown")
            url = f"https://www.youtube.com/watch?v={r.get('id')}"
            print(f"{i}. \x1b]8;;{url}\x1b\\{title} — {uploader}\x1b]8;;\x1b\\", flush=True)

        choice = (await async_input("Choose number to download (0=skip): ")).strip()
        if choice.isdigit() and 1 <= int(choice) <= len(results):
            sel = results[int(choice) - 1]
            playlist_names = await choose_playlists()
            entry = {"url": f"https://www.youtube.com/watch?v={sel.get('id')}", "input": query}
            tasks.append(asyncio.create_task(limit_downloads(entry, playlist_names)))

    if tasks:
        await asyncio.gather(*tasks)

# ------------------------
# Entry
# ------------------------
async def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)
    os.makedirs(ALL_SONGS, exist_ok=True)

    choice = await async_input("Do you want to (1) input a single song/query or (2) use songs.txt? ")
    if choice.strip() == "1":
        user_input = await async_input("Enter URL or search query: ")
        if "http" in user_input:
            # Treat as direct link
            title = await asyncio.to_thread(get_title_from_url, user_input)
            print(f"Processing: \x1b]8;;{user_input}\x1b\\{title}\x1b]8;;\x1b\\", flush=True)
            playlist_names = await choose_playlists()
            entry = {"url": user_input, "input": user_input}
            await limit_downloads(entry, playlist_names)
        else:
            # Treat as search query
            results = await search_youtube(user_input, max_results=5)
            if not results:
                print(f"No results for: {user_input}", flush=True)
                return

            print(f"\nResults for: {user_input}", flush=True)
            for i, r in enumerate(results, 1):
                title = r.get("title", "Unknown")
                uploader = r.get("uploader", "Unknown")
                url = f"https://www.youtube.com/watch?v={r.get('id')}"
                print(f"{i}. \x1b]8;;{url}\x1b\\{title} — {uploader}\x1b]8;;\x1b\\", flush=True)

            choice = (await async_input("Choose number to download (0=skip): ")).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(results):
                sel = results[int(choice) - 1]
                playlist_names = await choose_playlists()
                entry = {"url": f"https://www.youtube.com/watch?v={sel.get('id')}", "input": user_input}
                await limit_downloads(entry, playlist_names)
    else:
        await process_links()

if __name__ == "__main__":
    asyncio.run(main())
