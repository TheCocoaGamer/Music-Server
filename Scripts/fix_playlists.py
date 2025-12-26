import os

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

# folder w all ur .m3u playlists
PLAYLIST_DIR = os.environ['PLAYLISTS_DIR']

for file in os.listdir(PLAYLIST_DIR):
    if file.lower().endswith(".m3u"):
        path = os.path.join(PLAYLIST_DIR, file)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        valid_lines = []
        for line in lines:
            song_path = os.path.join(PLAYLIST_DIR, line)
            if os.path.exists(song_path):
                valid_lines.append(line)
            else:
                print(f"❌ missing: {line} in {file}")

        # write the good lines back
        with open(path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for line in valid_lines:
                f.write(f"{line}\n")

        print(f"✅ cleaned {file}: kept {len(valid_lines)} of {len(lines)}")
