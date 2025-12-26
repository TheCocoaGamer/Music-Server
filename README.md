# Music Server Setup

This repository contains a complete setup for a personal music streaming server using Navidrome, along with Python scripts for automated music downloading and playlist management.

## Features

- **Navidrome Music Server**: Web-based music streaming with playlist support, similar to Subsonic
- **Automated Music Downloads**: Download music from YouTube with automatic tagging and playlist management
- **Playlist Management**: Create and manage M3U playlists with embedded metadata
- **Reverse Proxy**: Caddy provides SSL encryption and secure access

## Prerequisites

- Windows 10 or 11
- Administrator privileges (for Caddy installation)
- Internet connection
- At least 4GB RAM recommended

## Installation Guide

Follow these steps in order on a fresh Windows PC.

### 1. Install Git

Git is required to download this repository.

1. Go to https://git-scm.com/download/win
2. Download the installer for Windows
3. Run the installer with default settings
4. Open Command Prompt and verify: `git --version`

### 2. Install Docker Desktop

Docker runs the Navidrome music server in a container.

1. Go to https://www.docker.com/products/docker-desktop
2. Download Docker Desktop for Windows
3. Run the installer (may require restart)
4. Launch Docker Desktop and let it start

### 3. Install Python

Python is needed for the music management scripts.

1. Go to https://www.python.org/downloads/
2. Download the latest Python 3.x installer
3. Run the installer
4. **Important**: Check "Add Python to PATH" during installation
5. Verify installation: Open Command Prompt and run `python --version`

### 4. Install Caddy

Caddy provides the web server and SSL certificate management.

1. Go to https://caddyserver.com/download
2. Download the Windows binary (zip file)
3. Extract the zip file to a permanent location (e.g., `C:\caddy\`)
4. Add the folder to your system PATH:
   - Search for "Environment Variables" in Windows search
   - Click "Environment Variables"
   - Under "System variables", find "Path" and click "Edit"
   - Add `C:\caddy\` (or your extraction folder)
5. Verify: Open Command Prompt and run `caddy version`

### 5. Clone the Repository

Download the setup files to your computer.

1. Open Command Prompt
2. Run: `git clone https://github.com/TheCocoaGamer/Music-Server.git`
3. Enter the directory: `cd Music-Server`

### 6. Create Music Directories

Set up the folder structure for your music.

1. In the `Music-Server` folder, create these directories:
   - `Songs` - Main music directory
   - `TempDownloads` - Temporary download folder
2. Optional: Place your existing music files in `Songs/AllSongs/`

### 7. Configure Environment Variables

Set up the configuration file with your paths.

1. Copy the example file: `copy "Scripts\.env.example" "Scripts\.env"`
2. Edit `Scripts\.env` with Notepad or any text editor:
   ```
   # Configuration file for paths and settings
   # Edit these values to match your system

   MUSIC_DIR=./Songs
   NAVIDROME_DIR=./Scripts/Navidrome
   DOMAIN=your-domain.com

   # Additional paths for Python scripts
   SONGS_FILE=./songs.txt
   TEMP_DIR=./TempDownloads
   PLAYLISTS_DIR=./Songs
   ALL_SONGS=./Songs/AllSongs
   ```

   **Important settings to customize:**
   - `DOMAIN`: Set to your domain name (e.g., `music.example.com`) or your PC's IP address (e.g., `192.168.1.100`)
   - All paths should be relative (starting with `./`) unless you need absolute paths

### 8. Install Dependencies

#### Python Libraries
Install required Python libraries for the music scripts.

1. Open Command Prompt in the `Music-Server` directory
2. Run: `pip install yt-dlp mutagen aiofiles`

#### FFmpeg
FFmpeg is required for audio conversion (MP3 extraction from videos).

1. Go to https://ffmpeg.org/download.html
2. Download the latest Windows build (static version)
3. Extract the zip file
4. Add the `bin` folder to your system PATH:
   - Copy the path to the `bin` folder (e.g., `C:\ffmpeg\bin`)
   - Follow the PATH instructions from step 4 (Caddy installation)
5. Verify: Open Command Prompt and run `ffmpeg -version`

### 9. Start the Services

Launch Navidrome and Caddy.

1. **Important**: Right-click `Scripts\Navidrome\start-services.bat` and select "Run as administrator"
2. The script will:
   - Start the Navidrome Docker container
   - Start Caddy web server
3. Wait for services to fully start (may take 1-2 minutes)

**Note**: The script runs in the background and will create a startup script that automatically starts these services when Windows boots. Manual running is only required for initial setup and troubleshooting. If needed, the background processes can be stopped through Task Manager.

### 10. Access Your Music Server

Open your web browser and go to:
- `https://your-domain.com` (if using a domain)
- `https://your-ip-address` (if using IP)
- `http://localhost:4533` (direct access, no SSL)

For remote access over the internet, consider using Tailscale for secure VPN access without traditional port forwarding.

**First-time login:**
- Username: `admin`
- Password: `admin`
- Change the password immediately after first login

### 11. Using the Python Scripts

The main script is `MusicGUI.py`, which provides a graphical interface for all music management functions.

#### Main GUI Script (`Scripts/MusicGUI.py`)

This is the primary tool for music management.

1. Run: `python Scripts/MusicGUI.py`
2. Use the interface to:
   - Download music from YouTube
   - Manage playlists
   - Configure settings

#### Other Scripts

- `Scripts/MusicDownload.py` - Command-line music downloader
- `Scripts/PlaylistManager.py` - Playlist editing tools
- `Scripts/fix_playlists.py` - Playlist repair utilities
- `Scripts/MusicSort(for Deezer Transfer).py` - Music file organization

To use any script, run: `python Scripts/scriptname.py`
