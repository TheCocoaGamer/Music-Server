import os
import shutil
from pathlib import Path
import difflib
from mutagen.id3 import ID3, COMM, ID3NoHeaderError

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
DEST_ROOT   = Path(os.environ['PLAYLISTS_DIR'])
ALL_SONGS   = DEST_ROOT / "AllSongs"
TEMP_DOWNLOADS = DEST_ROOT.parent / "TempDownloads"
PLAYLISTS   = DEST_ROOT

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".wma", ".aiff", ".alac"}
# ==========================


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS


def list_playlists() -> list[Path]:
    PLAYLISTS.mkdir(parents=True, exist_ok=True)
    return sorted(PLAYLISTS.glob("*.m3u"))


def find_song_matches(term: str):
    """Fuzzy search songs in AllSongs and TempDownloads."""
    all_songs = []
    if ALL_SONGS.exists():
        all_songs.extend([s for s in ALL_SONGS.glob("*") if s.is_file() and is_audio(s)])
    if TEMP_DOWNLOADS.exists():
        all_songs.extend([s for s in TEMP_DOWNLOADS.glob("*") if s.is_file() and is_audio(s)])
    names = [s.stem for s in all_songs]

    # Use difflib to get close matches
    close = difflib.get_close_matches(term, names, n=15, cutoff=0.3)  # generous
    matches = [s for s in all_songs if s.stem in close]

    # Also include substring matches
    term_lower = term.lower()
    substring_matches = [s for s in all_songs if term_lower in s.stem.lower()]

    # Merge results without duplicates
    seen = set()
    final = []
    for s in matches + substring_matches:
        if s not in seen:
            seen.add(s)
            final.append(s)
    return final


def song_playlists(song_path: Path) -> list[Path]:
    """Return list of playlist files that contain the song."""
    rel = os.path.relpath(song_path, PLAYLISTS).replace("\\", "/")
    pls = []
    for pl in list_playlists():
        lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
        if rel in lines:
            pls.append(pl)
    return pls


def set_playlists_for_songs(song_paths: list[Path], keep_indices: list[int]):
    """Apply playlist selections to multiple songs."""
    all_pls = list_playlists()
    chosen = [all_pls[i] for i in keep_indices if 0 <= i < len(all_pls)]

    # Move songs from TempDownloads to AllSongs if adding to playlists
    if keep_indices:  # if adding to any playlists
        for i, song_path in enumerate(song_paths):
            if song_path.parent == TEMP_DOWNLOADS:
                new_path = ALL_SONGS / song_path.name
                if not new_path.exists():
                    shutil.move(str(song_path), str(new_path))
                    print(f"📁 Moved {song_path.name} from TempDownloads to AllSongs")
                    song_paths[i] = new_path
                else:
                    print(f"⚠️ {song_path.name} already exists in AllSongs, skipping move")

    for song_path in song_paths:
        rel = os.path.relpath(song_path, PLAYLISTS).replace("\\", "/")

        # Remove from all others
        for pl in all_pls:
            lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
            new_lines = [ln for ln in lines if ln.strip() and ln != rel]
            if lines != new_lines:
                pl.write_text("\n".join(new_lines), encoding="utf-8")
                if pl not in chosen:
                    print(f"🗑 Removed {song_path.name} from {pl.stem}")

        # Add to chosen
        for pl in chosen:
            lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines() if pl.exists() else []
            if not lines or lines[0] != "#EXTM3U":
                if not lines or lines[0].strip() != "#EXTM3U":
                    lines.insert(0, "#EXTM3U")
            if rel not in lines:
                lines.append(rel)
                pl.write_text("\n".join(lines), encoding="utf-8")
                print(f"✅ Added {song_path.name} to {pl.stem}")

    # Update MP3 comments with current playlists
    for song_path in song_paths:
        if song_path.suffix.lower() == ".mp3":
            playlists = [pl.stem for pl in song_playlists(song_path)]
            tag_song_with_playlists(str(song_path), playlists)

    # Move songs with no playlists from AllSongs to TempDownloads
    for i, song_path in enumerate(song_paths):
        if song_path.parent == ALL_SONGS and not song_playlists(song_path):
            new_path = TEMP_DOWNLOADS / song_path.name
            if not new_path.exists():
                shutil.move(str(song_path), str(new_path))
                print(f"📁 Moved {song_path.name} from AllSongs to TempDownloads (no playlists)")
                song_paths[i] = new_path
            else:
                print(f"⚠️ {song_path.name} already exists in TempDownloads, skipping move")


def delete_song(song_path: Path):
    # Remove from all playlists
    for pl in song_playlists(song_path):
        lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
        rel = os.path.relpath(song_path, PLAYLISTS).replace("\\", "/")
        new_lines = [ln for ln in lines if ln.strip() and ln != rel]
        pl.write_text("\n".join(new_lines), encoding="utf-8")
    # Delete from AllSongs
    if song_path.exists():
        song_path.unlink()
        print(f"❌ Deleted {song_path.name} from AllSongs.")


def tag_song_with_playlists(song_path: str, playlists: list[str]):
    """
    Writes all playlist names into the comment field of the MP3.
    """
    comment_text = ", ".join(playlists)

    try:
        tags = ID3(song_path)
    except ID3NoHeaderError:
        tags = ID3()  # create new ID3 tag block if missing

    tags.delall("COMM")  # remove old comments
    tags.add(COMM(encoding=3, lang="eng", desc="", text=comment_text))

    # Save in ID3v2.3 (most compatible with Explorer/Foobar)
    tags.save(song_path, v2_version=3)

    print(f"✅ {os.path.basename(song_path)} → {comment_text}")


def cleanup_orphaned_songs():
    """Move songs from AllSongs to TempDownloads if they have no playlists."""
    if not ALL_SONGS.exists():
        return
    for song_path in ALL_SONGS.glob("*"):
        if song_path.is_file() and is_audio(song_path):
            if not song_playlists(song_path):
                new_path = TEMP_DOWNLOADS / song_path.name
                if not new_path.exists():
                    shutil.move(str(song_path), str(new_path))
                    print(f"📁 Moved {song_path.name} from AllSongs to TempDownloads (no playlists)")
                else:
                    print(f"⚠️ {song_path.name} already exists in TempDownloads, skipping move")


def create_new_playlist():
    name = input("Enter new playlist name: ").strip()
    if not name:
        return None
    pl_path = PLAYLISTS / f"{name}.m3u"
    if not pl_path.exists():
        pl_path.write_text("#EXTM3U\n", encoding="utf-8")
        print(f"📁 Created new playlist: {name}")
    return pl_path


def add_songs_to_playlist(song_paths: list[Path], playlist_path: Path):
    """Add songs to a specific playlist."""
    rels = [os.path.relpath(song_path, PLAYLISTS).replace("\\", "/") for song_path in song_paths]
    lines = playlist_path.read_text(encoding="utf-8", errors="ignore").splitlines() if playlist_path.exists() else []
    if not lines or lines[0] != "#EXTM3U":
        lines.insert(0, "#EXTM3U")
    for rel in rels:
        if rel not in lines:
            lines.append(rel)
    playlist_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✅ Added {len(song_paths)} songs to {playlist_path.stem}")


def song_changer():
    """Search and manage songs across all playlists."""
    while True:
        term = input("\nEnter search term (or 'q' to quit): ").strip()
        if term.lower() == "q":
            break

        matches = find_song_matches(term)
        if not matches:
            print("No matches found.")
            continue

        print("\nMatches:")
        for i, song in enumerate(matches, 1):
            print(f" {i}. {song.name}")

        choice = input("Choose numbers (comma/space separated, 0=cancel): ").strip()
        if not choice or choice == "0":
            continue

        indices = [int(x) - 1 for x in choice.replace(",", " ").split() if x.isdigit()]
        chosen_songs = [matches[i] for i in indices if 0 <= i < len(matches)]
        if not chosen_songs:
            continue

        print("\nSelected songs:")
        for s in chosen_songs:
            print(f" - {s.name}")

        # Show playlists
        all_pls = list_playlists()
        songs_pls = {pl.stem for song in chosen_songs for pl in song_playlists(song)}

        print("\nAvailable playlists:")
        for i, pl in enumerate(all_pls, 1):
            mark = "✓" if pl.stem in songs_pls else " "
            print(f" {i}. [{mark}] {pl.stem}")

        print("\nType numbers (comma/space separated) for playlists to KEEP (applies to all songs)")
        print("Or press 'n' to create new playlist, 'd' to delete selected songs, '0' to cancel.")

        while True:
            user_in = input("> ").strip().lower()

            if user_in == "0":
                break
            elif user_in == "d":
                confirm = input("Are you sure you want to DELETE these songs? (y/n): ").strip().lower()
                if confirm == "y":
                    for song in chosen_songs:
                        delete_song(song)
                break
            elif user_in == "n":
                new_pl = create_new_playlist()
                if new_pl:
                    all_pls = list_playlists()  # refresh list
                    songs_pls = {pl.stem for song in chosen_songs for pl in song_playlists(song)}
                    for i, pl in enumerate(all_pls, 1):
                        mark = "✓" if pl.stem in songs_pls else " "
                        print(f" {i}. [{mark}] {pl.stem}")
                continue
            else:
                try:
                    nums = [int(x) - 1 for x in user_in.replace(",", " ").split() if x.isdigit()]
                    set_playlists_for_songs(chosen_songs, nums)
                except Exception as e:
                    print(f"Invalid input: {e}")
                break


def playlist_cleanse():
    """Remove songs from a specific playlist."""
    all_pls = list_playlists()
    if not all_pls:
        print("No playlists found.")
        return

    print("\nAvailable playlists:")
    for i, pl in enumerate(all_pls, 1):
        print(f" {i}. {pl.stem}")

    choice = input("Choose playlist number (0=cancel): ").strip()
    if not choice or choice == "0":
        return

    try:
        pl_idx = int(choice) - 1
        if not (0 <= pl_idx < len(all_pls)):
            print("Invalid choice.")
            return
        pl = all_pls[pl_idx]
    except ValueError:
        print("Invalid input.")
        return

    # Get songs in playlist
    songs_in_pl = []
    for song in (list(ALL_SONGS.glob("*")) if ALL_SONGS.exists() else []) + (list(TEMP_DOWNLOADS.glob("*")) if TEMP_DOWNLOADS.exists() else []):
        if is_audio(song) and pl in song_playlists(song):
            songs_in_pl.append(song)

    if not songs_in_pl:
        print(f"No songs in playlist {pl.stem}.")
        return

    songs_in_pl.sort(key=lambda x: x.name.lower())

    print(f"\nSongs in {pl.stem} (alphabetical):")
    for i, song in enumerate(songs_in_pl, 1):
        print(f" {i}. {song.name}")

    choice = input("Choose songs to remove (comma/space separated, 0=cancel): ").strip()
    if not choice or choice == "0":
        return

    indices = [int(x) - 1 for x in choice.replace(",", " ").split() if x.isdigit()]
    to_remove = [songs_in_pl[i] for i in indices if 0 <= i < len(songs_in_pl)]

    if not to_remove:
        return

    # Remove from playlist
    rels_to_remove = [os.path.relpath(song, PLAYLISTS).replace("\\", "/") for song in to_remove]
    lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
    new_lines = [ln for ln in lines if ln not in rels_to_remove]
    pl.write_text("\n".join(new_lines), encoding="utf-8")
    print(f"🗑 Removed {len(to_remove)} songs from {pl.stem}")

    # Move to TempDownloads if no playlists left
    for i, song in enumerate(to_remove):
        if not song_playlists(song) and song.parent == ALL_SONGS:
            new_path = TEMP_DOWNLOADS / song.name
            if not new_path.exists():
                shutil.move(str(song), str(new_path))
                print(f"📁 Moved {song.name} from AllSongs to TempDownloads (no playlists)")
                to_remove[i] = new_path  # update path for tagging
            else:
                print(f"⚠️ {song.name} already exists in TempDownloads, skipping")

    # Update tags
    for song in to_remove:
        if song.suffix.lower() == ".mp3":
            playlists = [p.stem for p in song_playlists(song)]
            tag_song_with_playlists(str(song), playlists)


def playlist_bulk():
    """Add songs to a playlist with multiple queries."""
    all_pls = list_playlists()
    if not all_pls:
        print("No playlists found.")
        return

    print("\nAvailable playlists:")
    for i, pl in enumerate(all_pls, 1):
        print(f" {i}. {pl.stem}")

    choice = input("Choose playlist number (0=cancel): ").strip()
    if not choice or choice == "0":
        return

    try:
        pl_idx = int(choice) - 1
        if not (0 <= pl_idx < len(all_pls)):
            print("Invalid choice.")
            return
        pl = all_pls[pl_idx]
    except ValueError:
        print("Invalid input.")
        return

    print(f"\nAdding songs to {pl.stem}. Enter '0' to finish.")

    while True:
        term = input("Enter search term (0 to finish): ").strip()
        if term == "0":
            break

        matches = find_song_matches(term)
        if not matches:
            print("No matches found.")
            continue

        print("\nMatches:")
        for i, song in enumerate(matches, 1):
            print(f" {i}. {song.name}")

        choice = input("Choose songs to add (comma/space separated, 0=cancel): ").strip()
        if not choice or choice == "0":
            continue

        indices = [int(x) - 1 for x in choice.replace(",", " ").split() if x.isdigit()]
        chosen_songs = [matches[i] for i in indices if 0 <= i < len(matches)]
        if not chosen_songs:
            continue

        # Move from TempDownloads to AllSongs
        for i, song in enumerate(chosen_songs):
            if song.parent == TEMP_DOWNLOADS:
                new_path = ALL_SONGS / song.name
                if not new_path.exists():
                    shutil.move(str(song), str(new_path))
                    print(f"📁 Moved {song.name} from TempDownloads to AllSongs")
                    chosen_songs[i] = new_path
                else:
                    print(f"⚠️ {song.name} already exists in AllSongs, skipping")

        # Add to playlist
        add_songs_to_playlist(chosen_songs, pl)

        # Update tags
        for song in chosen_songs:
            if song.suffix.lower() == ".mp3":
                playlists = [p.stem for p in song_playlists(song)]
                tag_song_with_playlists(str(song), playlists)


def main():
    if not ALL_SONGS.exists() and not TEMP_DOWNLOADS.exists():
        print(f"ERROR: Neither AllSongs nor TempDownloads folders found: {ALL_SONGS}, {TEMP_DOWNLOADS}")
        return

    # Clean up orphaned songs at startup
    cleanup_orphaned_songs()

    while True:
        print("\nMain Menu:")
        print("1. Song Changer - Search all songs, manage playlists")
        print("2. Playlist Cleanse - Remove songs from a specific playlist")
        print("3. Playlist Bulk - Add songs to a playlist with multiple queries")
        choice = input("Choose option (1-3, or 'q' to quit): ").strip()

        if choice.lower() == "q":
            break
        elif choice == "1":
            song_changer()
        elif choice == "2":
            playlist_cleanse()
        elif choice == "3":
            playlist_bulk()
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
