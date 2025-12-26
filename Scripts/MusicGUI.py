import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import asyncio
import threading
import os
import shutil
from pathlib import Path
import difflib
import random
from yt_dlp import YoutubeDL
from mutagen.id3 import ID3, COMM, APIC, TPE1, ID3NoHeaderError
import aiofiles
import urllib.request

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

# Import config from existing scripts
SONGS_FILE = os.environ['SONGS_FILE']
TEMP_DIR = os.environ['TEMP_DIR']
PLAYLISTS_DIR = os.environ['PLAYLISTS_DIR']
ALL_SONGS = os.environ['ALL_SONGS']
MAX_CONCURRENT = 10

DEST_ROOT = Path(os.environ['PLAYLISTS_DIR'])
ALL_SONGS_PATH = DEST_ROOT / "AllSongs"
TEMP_DOWNLOADS = DEST_ROOT.parent / "TempDownloads"
PLAYLISTS = DEST_ROOT

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".wma", ".aiff", ".alac"}

class MusicGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Manager GUI")
        self.root.geometry("800x660")
        self.root.resizable(True, True)

        # Set window icon for taskbar
        import sys
        icon_path = os.path.join(sys._MEIPASS, "mp3 downloader.png") if hasattr(sys, "_MEIPASS") else r"C:\Users\Yahwe\Pictures\Icons\mp3 downloader.png"
        self.root.iconphoto(False, tk.PhotoImage(file=icon_path))

        # Theme colors
        self.bg_color = '#0b0b0d'  # Root window
        self.main_frame_bg = '#111113'  # Main frame, notebook, tab frames, etc.
        self.label_frame_bg = '#151518'  # Status frame, label frames
        self.fg_color = '#e6e6e6'  # Foreground
        self.secondary_bg = '#18181b'  # Entry fields, etc.
        self.accent_color = '#d31745'  # Selections, active
        self.button_bg = '#ff1e56'  # Button background
        self.insert_color = '#ff1e56'  # Entry insert
        self.tab_fg = '#b3b3b3'  # Tab foreground
        self.tab_selected_fg = '#e6e6e6'  # Selected tab fg
        self.progress_bg = '#18181b'  # Progress canvas bg
        self.progress_fill = '#ff003c'  # Progress fill (solid for simplicity)

        # Configure dark theme with red accents using default theme
        self.style = ttk.Style(self.root)
        self.style.theme_use('default')
        # Keep default theme but configure specific styles
        self.style.configure('TFrame', background=self.main_frame_bg)
        self.style.configure('TLabel', background=self.main_frame_bg, foreground=self.fg_color)
        self.style.configure('TButton', background=self.button_bg, foreground=self.fg_color, borderwidth=0, relief='flat')
        self.style.map('TButton', background=[('active', self.button_bg), ('pressed', self.button_bg)])
        self.style.configure('TEntry', fieldbackground=self.secondary_bg, background=self.secondary_bg, foreground=self.fg_color, insertcolor=self.insert_color, borderwidth=0, relief='flat')
        self.style.configure('TCheckbutton', background=self.secondary_bg, foreground=self.fg_color, indicatorcolor='#333333', indicatorbackground=self.main_frame_bg)
        self.style.map('TCheckbutton', background=[('selected', self.secondary_bg)], indicatorcolor=[('selected', self.accent_color)])
        self.style.configure('TCombobox', fieldbackground=self.secondary_bg, background=self.secondary_bg, foreground=self.fg_color, arrowcolor=self.fg_color, borderwidth=0, relief='flat')
        self.style.map('TCombobox', fieldbackground=[('readonly', self.secondary_bg)], selectbackground=[('focus', self.accent_color)], selectforeground=[('focus', self.fg_color)])
        self.style.configure('TNotebook', background=self.main_frame_bg)
        self.style.configure('TNotebook.Tab', background=self.main_frame_bg, foreground=self.tab_fg)
        self.style.map('TNotebook.Tab', background=[('selected', self.accent_color)], foreground=[('selected', self.tab_selected_fg)])
        self.style.configure('TLabelFrame', background=self.label_frame_bg, foreground=self.fg_color, borderwidth=0, relief='flat')
        self.style.configure('TLabelFrame.Label', background=self.label_frame_bg, foreground=self.fg_color)
        self.style.configure('TCombobox.Listbox', background=self.main_frame_bg, foreground=self.fg_color, selectbackground=self.accent_color, selectforeground=self.fg_color)

        self.root.configure(bg=self.bg_color)

        # Batch state
        self.batch_mode = False
        self.batch_lines = []
        self.batch_index = 0
        self.random_mode = tk.BooleanVar()

        # Playlist vars for different tabs
        self.song_changer_playlist_vars = {}
        self.song_changer_playlist_checkbuttons = []
        self.single_playlist_vars = {}
        self.single_playlist_checkbuttons = []
        self.batch_playlist_vars = {}
        self.batch_playlist_checkbuttons = []

        # Track current column count to avoid unnecessary updates
        self.current_playlist_cols = self._get_playlist_cols()
        self.fixed_width = 800
        self.screen_height = self.root.winfo_screenheight() - 200  # Leave space for taskbar and other UI

        # Settings variables
        self.songs_file_var = tk.StringVar(value=SONGS_FILE)
        self.temp_dir_var = tk.StringVar(value=TEMP_DIR)
        self.playlists_dir_var = tk.StringVar(value=PLAYLISTS_DIR)
        self.all_songs_var = tk.StringVar(value=ALL_SONGS)

        # Create main layout
        self.main_frame = tk.Frame(root, bg=self.main_frame_bg)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Status frame at bottom with fixed height
        self.status_frame = tk.LabelFrame(self.main_frame, text="Status & Progress", bg=self.label_frame_bg, fg=self.fg_color, height=150)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
        self.status_frame.pack_propagate(False)  # Prevent shrinking

        # Create notebook for tabs (takes remaining space)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Status text
        self.status_text = tk.Text(self.status_frame, height=5, state=tk.DISABLED, bg=self.main_frame_bg, fg=self.fg_color)
        self.status_text.pack(fill=tk.X, padx=5, pady=5)

        # Custom progress bar with text inside
        progress_frame = tk.Frame(self.status_frame, bg=self.main_frame_bg)
        progress_frame.pack(fill=tk.X, padx=5, pady=(0,5))

        ttk.Label(progress_frame, text="Progress:").pack(side=tk.LEFT)
        self.progress_canvas = tk.Canvas(progress_frame, height=20, bg=self.progress_bg, relief='sunken', borderwidth=1)
        self.progress_canvas.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(5,5))

        self.percent_label = ttk.Label(progress_frame, text="0%")
        self.percent_label.pack(side=tk.LEFT)

        # Initialize progress
        self.progress_value = 0
        self.progress_text = "Ready"
        self.progress_canvas.bind('<Configure>', self._draw_progress)
        self._draw_progress()

        # Download Song tab
        self.download_single_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.download_single_frame, text="Download Song")
        self.setup_download_single_tab()

        # Batch Download tab
        self.download_batch_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.download_batch_frame, text="Batch Download")
        self.setup_download_batch_tab()

        # Playlist Changer tab
        self.song_changer_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.song_changer_frame, text="Playlist Changer")
        self.setup_song_changer()

        # Playlist Cleanse tab
        self.cleanse_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.cleanse_frame, text="Playlist Cleanse")
        self.setup_playlist_cleanse()

        # Playlist Bulk tab
        self.bulk_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.bulk_frame, text="Playlist Bulk")
        self.setup_playlist_bulk()

        # Auto Clean tab
        self.auto_clean_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.auto_clean_frame, text="Auto Clean")
        self.setup_auto_clean_tab()

        # Settings tab
        self.settings_frame = tk.Frame(self.notebook, bg=self.main_frame_bg)
        self.notebook.add(self.settings_frame, text="Settings")
        self.setup_settings_tab()

        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(PLAYLISTS_DIR, exist_ok=True)
        os.makedirs(ALL_SONGS, exist_ok=True)

        self.update_playlist_checkbuttons()
        self.update_playlist_list()
        self.update_single_playlist_checkbuttons()
        self.update_batch_playlist_checkbuttons()

        # Bind to window resize to update grid
        self.root.bind('<Configure>', self._on_window_resize)

    def setup_download_single_tab(self):
        # Input frame
        input_frame = tk.LabelFrame(self.download_single_frame, text="Input", bg=self.label_frame_bg, fg=self.fg_color)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # Use grid for better control
        input_frame.columnconfigure(0, weight=1)

        self.single_url_entry = ttk.Entry(input_frame)
        self.single_url_entry.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=(5,0))
        self.single_url_entry.insert(0, "Enter URL or search query")
        self.single_url_entry.config(foreground="gray")
        self.single_url_entry.bind("<FocusIn>", self._on_single_entry_focus_in)
        self.single_url_entry.bind("<FocusOut>", self._on_single_entry_focus_out)
        self.single_url_entry.bind("<Return>", lambda e: self.process_single_download())

        self.single_process_button = tk.Button(input_frame, text="Process", command=self.process_single_download, bg=self.button_bg, fg=self.fg_color)
        self.single_process_button.grid(row=1, column=0, pady=(5,5))

        # Results frame
        self.single_results_frame = tk.LabelFrame(self.download_single_frame, text="Results", bg=self.label_frame_bg, fg=self.fg_color)
        self.single_results_frame.pack(fill=tk.X, padx=10, pady=5)

        self.single_results_listbox = tk.Listbox(self.single_results_frame, selectmode=tk.SINGLE, height=5, bg=self.main_frame_bg, fg=self.fg_color, selectbackground=self.accent_color)
        self.single_results_listbox.pack(fill=tk.X, padx=5, pady=5)
        self.single_results_listbox.bind("<Double-1>", self.open_single_video_link)

        # Download buttons
        button_frame = tk.Frame(self.download_single_frame, bg=self.main_frame_bg)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Download Selected", command=self.start_single_download, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5)

        # Playlist selection
        playlist_frame = tk.LabelFrame(self.download_single_frame, text="Playlists", bg=self.label_frame_bg, fg=self.fg_color)
        playlist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.single_playlist_checkbuttons_frame = tk.Frame(playlist_frame, bg=self.main_frame_bg)
        self.single_playlist_checkbuttons_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_single_playlist_checkbuttons()

        tk.Button(playlist_frame, text="+ Create New", command=self.create_new_playlist, bg=self.button_bg, fg=self.fg_color).pack(pady=5)

    def setup_download_batch_tab(self):
        # Input frame
        input_frame = tk.LabelFrame(self.download_batch_frame, text="", bg=self.label_frame_bg, fg=self.fg_color)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # Use grid for better control
        input_frame.columnconfigure(0, weight=1)

        self.batch_current_song_label = ttk.Label(input_frame, text="", anchor="w", relief="flat", background=self.secondary_bg, foreground=self.fg_color)
        self.batch_current_song_label.grid(row=0, column=0, sticky="ew", pady=(5,0))

        self.batch_process_button = tk.Button(input_frame, text="Process List", command=self.process_batch_download, bg=self.button_bg, fg=self.fg_color)
        self.batch_process_button.grid(row=1, column=0, pady=(5,5))

        # Results frame
        self.batch_results_frame = tk.LabelFrame(self.download_batch_frame, text="Results", bg=self.label_frame_bg, fg=self.fg_color)
        self.batch_results_frame.pack(fill=tk.X, padx=10, pady=5)

        self.batch_results_listbox = tk.Listbox(self.batch_results_frame, selectmode=tk.SINGLE, height=5, bg=self.main_frame_bg, fg=self.fg_color, selectbackground=self.accent_color)
        self.batch_results_listbox.pack(fill=tk.X, padx=5, pady=5)
        self.batch_results_listbox.bind("<Double-1>", self.open_batch_video_link)

        # Download buttons
        button_frame = tk.Frame(self.download_batch_frame, bg=self.main_frame_bg)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Download Selected", command=self.start_batch_download, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5)
        self.skip_button = tk.Button(button_frame, text="Skip Current", command=self.skip_current_batch, bg=self.button_bg, fg=self.fg_color)
        self.skip_button.pack(side=tk.LEFT, padx=5)
        self.skip_button.pack_forget()  # Hide initially
        self.random_check = ttk.Checkbutton(button_frame, text="Random Order", variable=self.random_mode)
        self.random_check.pack(side=tk.LEFT, padx=5)

        # Playlist selection (optional for batch)
        playlist_frame = tk.LabelFrame(self.download_batch_frame, text="Playlists", bg=self.label_frame_bg, fg=self.fg_color)
        playlist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.batch_playlist_checkbuttons_frame = tk.Frame(playlist_frame, bg=self.main_frame_bg)
        self.batch_playlist_checkbuttons_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_batch_playlist_checkbuttons()

        tk.Button(playlist_frame, text="+ Create New", command=self.create_new_playlist, bg=self.button_bg, fg=self.fg_color).pack(pady=5)



    def setup_song_changer(self):
        # Search
        search_frame = tk.LabelFrame(self.song_changer_frame, text="Search Songs", bg=self.label_frame_bg, fg=self.fg_color)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        # Use grid for layout
        search_frame.columnconfigure(0, weight=1)

        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.grid(row=0, column=0, sticky=tk.EW, padx=(5,0), pady=5)
        self.search_entry.bind("<Return>", lambda e: self.song_changer_search())

        tk.Button(search_frame, text="Search", command=self.song_changer_search, bg=self.button_bg, fg=self.fg_color).grid(row=0, column=1, padx=(5,5), pady=5)

        # Results
        results_frame = tk.LabelFrame(self.song_changer_frame, text="Matches", bg=self.label_frame_bg, fg=self.fg_color)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.song_matches_listbox = tk.Listbox(results_frame, selectmode=tk.SINGLE, bg=self.main_frame_bg, fg=self.fg_color, selectbackground=self.accent_color)
        self.song_matches_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.song_matches_listbox.bind("<<ListboxSelect>>", self.update_playlist_checks_for_song)
        self.song_matches_listbox.bind("<Double-1>", self.open_song_file)

        # Playlists
        playlist_frame = tk.LabelFrame(self.song_changer_frame, text="Playlists", bg=self.label_frame_bg, fg=self.fg_color)
        playlist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.song_changer_playlist_checks_frame = tk.Frame(playlist_frame, bg=self.main_frame_bg)
        self.song_changer_playlist_checks_frame.pack(fill=tk.X, padx=5, pady=5)

        button_frame = tk.Frame(playlist_frame, bg=self.main_frame_bg)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(button_frame, text="+ Create New", command=self.create_new_playlist, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Label(button_frame, text="").pack(side=tk.LEFT, expand=True)
        tk.Button(button_frame, text="Clear Playlists", command=self.clear_playlists_selected_songs, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(button_frame, text="Apply Changes", command=self.apply_song_changes, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5, pady=5)

    def setup_playlist_cleanse(self):
        # Select playlist
        select_frame = tk.LabelFrame(self.cleanse_frame, text="Select Playlist", bg=self.label_frame_bg, fg=self.fg_color)
        select_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cleanse_playlist_var = tk.StringVar()
        self.cleanse_playlist_menu = None
        self.update_cleanse_menu()

        tk.Button(select_frame, text="Load Songs", command=self.load_playlist_songs, bg=self.button_bg, fg=self.fg_color).pack(pady=5)

        # Songs in playlist
        songs_frame = tk.LabelFrame(self.cleanse_frame, text="Songs in Playlist", bg=self.label_frame_bg, fg=self.fg_color)
        songs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.cleanse_songs_listbox = tk.Listbox(songs_frame, selectmode=tk.MULTIPLE, bg=self.main_frame_bg, fg=self.fg_color, selectbackground=self.accent_color)
        self.cleanse_songs_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tk.Button(self.cleanse_frame, text="Remove Selected", command=self.remove_from_playlist, bg=self.button_bg, fg=self.fg_color).pack(pady=10)

    def setup_playlist_bulk(self):
        # Select playlist
        select_frame = tk.LabelFrame(self.bulk_frame, text="Select Target Playlist", bg=self.label_frame_bg, fg=self.fg_color)
        select_frame.pack(fill=tk.X, padx=10, pady=5)

        self.bulk_playlist_var = tk.StringVar()
        self.bulk_playlist_menu = None
        self.update_bulk_menu()

        # Search
        search_frame = tk.LabelFrame(self.bulk_frame, text="Search Songs", bg=self.label_frame_bg, fg=self.fg_color)
        search_frame.pack(fill=tk.X, padx=10, pady=5)

        self.bulk_search_entry = ttk.Entry(search_frame)
        self.bulk_search_entry.pack(fill=tk.X, padx=5, pady=5)
        self.bulk_search_entry.bind("<Return>", lambda e: self.bulk_search())

        tk.Button(search_frame, text="Search", command=self.bulk_search, bg=self.button_bg, fg=self.fg_color).pack(pady=5)

        # Results
        results_frame = tk.LabelFrame(self.bulk_frame, text="Matches", bg=self.label_frame_bg, fg=self.fg_color)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.bulk_matches_listbox = tk.Listbox(results_frame, selectmode=tk.MULTIPLE, bg=self.main_frame_bg, fg=self.fg_color, selectbackground=self.accent_color)
        self.bulk_matches_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Buttons
        button_frame = tk.Frame(self.bulk_frame, bg=self.main_frame_bg)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(button_frame, text="Add Selected", command=self.add_selected_bulk, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(button_frame, text="Finish", command=self.finish_bulk, bg=self.button_bg, fg=self.fg_color).pack(side=tk.LEFT, padx=5, pady=5)

        # Current additions
        self.bulk_added_label = ttk.Label(self.bulk_frame, text="Songs added: 0")
        self.bulk_added_label.pack(pady=5)

    def setup_auto_clean_tab(self):
        ttk.Label(self.auto_clean_frame, text="This will move all songs from AllSongs that have no playlists to TempDownloads.").pack(pady=10)
        tk.Button(self.auto_clean_frame, text="Clean Orphaned Songs", command=self.run_auto_clean, bg=self.button_bg, fg=self.fg_color).pack(pady=10)

    def setup_settings_tab(self):
        self.settings_frame.columnconfigure(1, weight=1)

        ttk.Label(self.settings_frame, text="Max Concurrent Downloads:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_concurrent_var = tk.StringVar(value=str(MAX_CONCURRENT))
        spin = tk.Spinbox(self.settings_frame, from_=1, to=50, textvariable=self.max_concurrent_var, bg=self.secondary_bg, fg=self.fg_color)
        spin.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Button(self.settings_frame, text="Save", command=self.save_max_concurrent, bg=self.button_bg, fg=self.fg_color).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self.settings_frame, text="Songs File:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.songs_file_var).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        tk.Button(self.settings_frame, text="Open", command=self.open_songs_file, bg=self.button_bg, fg=self.fg_color).grid(row=1, column=2, padx=5, pady=5)

        ttk.Label(self.settings_frame, text="Temp Directory:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.temp_dir_var).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(self.settings_frame, text="Playlists Directory:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.playlists_dir_var).grid(row=3, column=1, sticky=tk.EW, padx=5, pady=5)

        ttk.Label(self.settings_frame, text="All Songs Directory:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(self.settings_frame, textvariable=self.all_songs_var).grid(row=4, column=1, sticky=tk.EW, padx=5, pady=5)

        tk.Button(self.settings_frame, text="Save Settings", command=self.save_settings, bg=self.button_bg, fg=self.fg_color).grid(row=5, column=0, columnspan=3, pady=5)

    def update_playlist_list(self):
        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        self.update_cleanse_menu()
        self.update_bulk_menu()

    def update_playlist_listbox(self):
        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        self.playlist_listbox.delete(0, tk.END)
        for pl in playlists:
            self.playlist_listbox.insert(tk.END, pl)

    def log_status(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def process_download(self):
        mode = self.download_mode.get()
        if mode == "single":
            query = self.url_entry.get().strip()
            if not query:
                messagebox.showerror("Error", "Enter a URL or search query")
                return
            self.process_single_download(query)
        else:
            self.process_batch_download()

    def process_single_download(self, query=None):
        if query is None:
            query = self.single_url_entry.get().strip()
        if not query:
            messagebox.showerror("Error", "Enter a URL or search query")
            return
        # Run search in thread
        threading.Thread(target=self._search_single_youtube, args=(query,)).start()

    def _search_single_youtube(self, query):
        self.log_status(f"Searching for: {query}")
        try:
            results = search_youtube_sync(query, max_results=5)
            self.root.after(0, self.display_single_search_results, results, query)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Search failed: {e}"))

    def display_single_search_results(self, results, original_query):
        self.single_results_listbox.delete(0, tk.END)
        self.single_search_results = results
        self.single_original_query = original_query
        for i, r in enumerate(results, 1):
            title = r.get("title", "Unknown")
            uploader = r.get("uploader", "Unknown")
            self.single_results_listbox.insert(tk.END, f"{i}. {title} — {uploader}")

    def start_single_download(self):
        selected = self.single_results_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Select a result to download")
            return
        index = selected[0]
        sel = self.single_search_results[index]
        playlists = [pl for pl in self.single_playlist_vars if self.single_playlist_vars[pl].get()]
        entry = {"url": f"https://www.youtube.com/watch?v={sel.get('id')}", "input": self.single_original_query}
        threading.Thread(target=self._download_song, args=(entry, playlists)).start()

    def open_single_video_link(self, event):
        selected = self.single_results_listbox.curselection()
        if selected:
            index = selected[0]
            sel = self.single_search_results[index]
            url = f"https://www.youtube.com/watch?v={sel.get('id')}"
            import webbrowser
            webbrowser.open(url)

    def _on_single_entry_focus_in(self, event):
        if self.single_url_entry.get() == "Enter URL or search query":
            self.single_url_entry.delete(0, tk.END)
            self.single_url_entry.config(foreground=self.fg_color)

    def _on_single_entry_focus_out(self, event):
        if not self.single_url_entry.get():
            self.single_url_entry.insert(0, "Enter URL or search query")
            self.single_url_entry.config(foreground="gray")

    def _search_youtube(self, query):
        self.log_status(f"Searching for: {query}")
        try:
            results = search_youtube_sync(query, max_results=5)
            self.root.after(0, self.display_search_results, results, query)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Search failed: {e}"))

    def display_search_results(self, results, original_query):
        self.results_listbox.delete(0, tk.END)
        self.search_results = results
        self.original_query = original_query
        for i, r in enumerate(results, 1):
            title = r.get("title", "Unknown")
            uploader = r.get("uploader", "Unknown")
            self.results_listbox.insert(tk.END, f"{i}. {title} — {uploader}")

    def start_download(self):
        selected = self.results_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Select a result to download")
            return
        index = selected[0]
        sel = self.search_results[index]
        playlists = [pl for pl in self.download_playlist_vars if self.download_playlist_vars[pl].get()]
        entry = {"url": f"https://www.youtube.com/watch?v={sel.get('id')}", "input": self.original_query}
        threading.Thread(target=self._download_song, args=(entry, playlists)).start()

    def _download_song(self, entry, playlists):
        # Start download in a separate thread so this function returns immediately
        threading.Thread(target=lambda: asyncio.run(download_song_gui(entry, playlists, self.log_status, self._update_progress))).start()
        # Immediately move to next item in batch mode
        if self.batch_mode:
            self.root.after(0, self.process_next_batch_item)

    def process_batch_download(self):
        try:
            with open(SONGS_FILE, "r", encoding="utf-8") as f:
                self.batch_lines = [line.strip() for line in f if line.strip()]
        except UnicodeDecodeError:
            with open(SONGS_FILE, "r", encoding="cp1252") as f:
                self.batch_lines = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            self.log_status("No songs.txt found; nothing to do.")
            return

        if self.random_mode.get():
            random.shuffle(self.batch_lines)

        self.batch_index = 0
        self.batch_mode = True
        self.skip_button.pack(side=tk.LEFT, padx=5)
        self.random_check.pack(side=tk.LEFT, padx=5)
        self.process_next_batch_item()

    def process_next_batch_item(self):
        if self.batch_index >= len(self.batch_lines):
            self.batch_lines = []
            self.batch_index = 0
            self.batch_mode = False
            self.skip_button.pack_forget()
            self.batch_current_song_label.config(text="")
            self.log_status("Batch processing completed.")
            return

        line = self.batch_lines[self.batch_index]
        self.batch_index += 1
        self.batch_current_song_label.config(text=line)

        if "http" in line:
            threading.Thread(target=self._process_batch_url, args=(line,)).start()
        else:
            threading.Thread(target=self._process_batch_query, args=(line,)).start()

    def display_batch_search_results(self, results, original_query):
        self.batch_results_listbox.delete(0, tk.END)
        self.batch_search_results = results
        self.batch_original_query = original_query
        for i, r in enumerate(results, 1):
            title = r.get("title", "Unknown")
            uploader = r.get("uploader", "Unknown")
            self.batch_results_listbox.insert(tk.END, f"{i}. {title} — {uploader}")

    def start_batch_download(self):
        selected = self.batch_results_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Select a result to download")
            return
        index = selected[0]
        sel = self.batch_search_results[index]
        playlists = [pl for pl in self.batch_playlist_vars if self.batch_playlist_vars[pl].get()]
        entry = {"url": f"https://www.youtube.com/watch?v={sel.get('id')}", "input": self.batch_original_query}
        threading.Thread(target=self._download_song, args=(entry, playlists)).start()

    def open_batch_video_link(self, event):
        selected = self.batch_results_listbox.curselection()
        if selected:
            index = selected[0]
            sel = self.batch_search_results[index]
            url = f"https://www.youtube.com/watch?v={sel.get('id')}"
            import webbrowser
            webbrowser.open(url)

    def skip_current_batch(self):
        self.process_next_batch_item()

    def _process_batch_url(self, line):
        try:
            title = get_title_from_url(line)
            self.root.after(0, lambda: self.display_batch_search_results([{"title": title, "uploader": "N/A", "id": line.split("v=")[-1] if "v=" in line else line}], line))
        except Exception as e:
            self.log_status(f"Error processing URL {line}: {e}")
            self.root.after(0, self.process_next_batch_item)

    def _process_batch_query(self, line):
        try:
            results = search_youtube_sync(line, max_results=5)
            if not results:
                self.log_status(f"No results for: {line}")
                self.root.after(0, self.process_next_batch_item)
                return
            self.root.after(0, lambda: self.display_batch_search_results(results, line))
        except Exception as e:
            self.log_status(f"Error processing query {line}: {e}")
            self.root.after(0, self.process_next_batch_item)



    def create_new_playlist(self):
        name = simpledialog.askstring("New Playlist", "Enter playlist name:")
        if name:
            pl_path = os.path.join(PLAYLISTS_DIR, f"{name}.m3u")
            if not os.path.exists(pl_path):
                with open(pl_path, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                self.log_status(f"Created playlist: {name}")
                self.update_playlist_list()
                self.update_playlist_checkbuttons()
                self.update_single_playlist_checkbuttons()
                self.update_batch_playlist_checkbuttons()
            else:
                messagebox.showerror("Error", "Playlist already exists")

    def update_playlist_checkbuttons(self):
        # Clear existing
        for cb in self.song_changer_playlist_checkbuttons:
            cb.destroy()
        self.song_changer_playlist_checkbuttons = []
        self.song_changer_playlist_vars = {}

        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        cols = self._get_playlist_cols()
        for i, pl in enumerate(playlists):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.song_changer_playlist_checks_frame, text=pl, variable=var)
            row = i // cols
            col = i % cols
            cb.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.song_changer_playlist_checkbuttons.append(cb)
            self.song_changer_playlist_vars[pl] = var

    def update_playlist_checkbuttons_download(self):
        # Clear existing
        for cb in self.download_playlist_checkbuttons:
            cb.destroy()
        self.download_playlist_checkbuttons = []
        self.download_playlist_vars = {}

        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        cols = self._get_playlist_cols()
        for i, pl in enumerate(playlists):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.playlist_checkbuttons_frame, text=pl, variable=var)
            row = i // cols
            col = i % cols
            cb.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.download_playlist_checkbuttons.append(cb)
            self.download_playlist_vars[pl] = var

    def update_single_playlist_checkbuttons(self):
        # Clear existing
        for cb in self.single_playlist_checkbuttons:
            cb.destroy()
        self.single_playlist_checkbuttons = []
        self.single_playlist_vars = {}

        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        cols = self._get_playlist_cols()
        for i, pl in enumerate(playlists):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.single_playlist_checkbuttons_frame, text=pl, variable=var)
            row = i // cols
            col = i % cols
            cb.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.single_playlist_checkbuttons.append(cb)
            self.single_playlist_vars[pl] = var

    def update_batch_playlist_checkbuttons(self):
        # Clear existing
        for cb in self.batch_playlist_checkbuttons:
            cb.destroy()
        self.batch_playlist_checkbuttons = []
        self.batch_playlist_vars = {}

        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        cols = self._get_playlist_cols()
        for i, pl in enumerate(playlists):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(self.batch_playlist_checkbuttons_frame, text=pl, variable=var)
            row = i // cols
            col = i % cols
            cb.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            self.batch_playlist_checkbuttons.append(cb)
            self.batch_playlist_vars[pl] = var

    def update_cleanse_menu(self):
        if self.cleanse_playlist_menu:
            self.cleanse_playlist_menu.destroy()
        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        if playlists:
            self.cleanse_playlist_menu = tk.OptionMenu(self.cleanse_frame.winfo_children()[0], self.cleanse_playlist_var, *playlists)
            self.cleanse_playlist_menu.config(bg=self.main_frame_bg, fg=self.fg_color, activebackground=self.accent_color)
            self.cleanse_playlist_menu.pack(fill=tk.X, padx=5, pady=5)
            menu = self.cleanse_playlist_menu['menu']
            menu.config(bg=self.main_frame_bg, fg=self.fg_color, activebackground=self.accent_color, activeforeground=self.fg_color)
        else:
            self.cleanse_playlist_var.set("")

    def update_bulk_menu(self):
        if self.bulk_playlist_menu:
            self.bulk_playlist_menu.destroy()
        playlists = [fn[:-4] for fn in sorted(os.listdir(PLAYLISTS_DIR)) if fn.endswith(".m3u")]
        if playlists:
            self.bulk_playlist_menu = tk.OptionMenu(self.bulk_frame.winfo_children()[0], self.bulk_playlist_var, *playlists)
            self.bulk_playlist_menu.config(bg=self.main_frame_bg, fg=self.fg_color, activebackground=self.accent_color)
            self.bulk_playlist_menu.pack(fill=tk.X, padx=5, pady=5)
            menu = self.bulk_playlist_menu['menu']
            menu.config(bg=self.main_frame_bg, fg=self.fg_color, activebackground=self.accent_color, activeforeground=self.fg_color)
        else:
            self.bulk_playlist_var.set("")

    def song_changer_search(self):
        term = self.search_entry.get().strip()
        if not term:
            return
        if term.startswith("http"):
            import webbrowser
            webbrowser.open(term)
            return
        threading.Thread(target=self._find_matches, args=(term,)).start()

    def _find_matches(self, term):
        matches = find_song_matches(term)
        self.root.after(0, self.display_song_matches, matches)

    def display_song_matches(self, matches):
        self.song_matches_listbox.delete(0, tk.END)
        self.song_matches_data = matches
        for song in matches:
            self.song_matches_listbox.insert(tk.END, song.name)
        if hasattr(self, 'last_selected_name'):
            for i, song in enumerate(matches):
                if song.name == self.last_selected_name:
                    self.song_matches_listbox.selection_set(i)
                    self.update_playlist_checks_for_song()
                    break
            del self.last_selected_name

    def apply_song_changes(self):
        selected = self.song_matches_listbox.curselection()
        if not selected:
            return
        self.last_selected_name = self.song_matches_data[selected[0]].name
        chosen_songs = [self.song_matches_data[i] for i in selected]
        keep_names = [pl for pl in self.song_changer_playlist_vars if self.song_changer_playlist_vars[pl].get()]
        threading.Thread(target=self._set_playlists, args=(chosen_songs, keep_names)).start()

    def _set_playlists(self, songs, keep_names):
        set_playlists_for_songs(songs, keep_names)
        self.root.after(0, lambda: (self.log_status("Playlists updated"), self.update_playlist_checks_for_song(), self.song_changer_search()))

    def clear_playlists_selected_songs(self):
        selected = self.song_matches_listbox.curselection()
        if not selected:
            return
        chosen_songs = [self.song_matches_data[i] for i in selected]
        for song in chosen_songs:
            # Remove from all playlists
            for pl in song_playlists(song):
                lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
                rel = os.path.relpath(song, PLAYLISTS).replace("\\", "/")
                new_lines = [ln for ln in lines if ln.strip() and ln != rel]
                pl.write_text("\n".join(new_lines), encoding="utf-8")
            # Tag with empty playlists
            if song.suffix.lower() == ".mp3" and song.exists():
                tag_song_with_playlists(str(song), [])
            # Move to TempDownloads if in AllSongs
            if song.parent == ALL_SONGS_PATH:
                new_path = TEMP_DOWNLOADS / song.name
                if not new_path.exists():
                    shutil.move(str(song), str(new_path))
                    self.log_status(f"Cleared playlists and moved {song.name} to TempDownloads")
                    # Update the path in song_matches_data
                    for i, s in enumerate(self.song_matches_data):
                        if s == song:
                            self.song_matches_data[i] = new_path
                            break
                else:
                    self.log_status(f"Cleared playlists for {song.name} (already exists in TempDownloads)")
            else:
                self.log_status(f"Cleared playlists for {song.name}")
        self.log_status("Playlists cleared for selected songs")
        # Refresh the checkboxes for the selected song
        self.update_playlist_checks_for_song()

    def load_playlist_songs(self):
        pl_name = self.cleanse_playlist_var.get()
        if not pl_name:
            return
        pl_path = PLAYLISTS / f"{pl_name}.m3u"
        if not pl_path.exists():
            return
        lines = pl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        rel_paths = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
        songs = []
        for rel in rel_paths:
            song_path = PLAYLISTS / rel
            if song_path.exists() and is_audio(song_path):
                songs.append(song_path)
        self.cleanse_songs_listbox.delete(0, tk.END)
        self.cleanse_songs_data = songs
        for song in songs:
            self.cleanse_songs_listbox.insert(tk.END, song.name)

    def remove_from_playlist(self):
        selected = self.cleanse_songs_listbox.curselection()
        if not selected:
            return
        to_remove = [self.cleanse_songs_data[i] for i in selected]
        pl_name = self.cleanse_playlist_var.get()
        rels_to_remove = [os.path.relpath(song, PLAYLISTS).replace("\\", "/") for song in to_remove]
        pl_path = PLAYLISTS / f"{pl_name}.m3u"
        lines = pl_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        new_lines = [ln for ln in lines if ln not in rels_to_remove]
        pl_path.write_text("\n".join(new_lines), encoding="utf-8")
        self.log_status(f"Removed {len(to_remove)} songs from {pl_name}")
        # Update tags and move if needed
        for song in to_remove:
            should_move = not song_playlists(song) and song.parent == ALL_SONGS_PATH
            if should_move:
                new_path = TEMP_DOWNLOADS / song.name
                if not new_path.exists():
                    # Tag before moving
                    if song.suffix.lower() == ".mp3":
                        tag_song_with_playlists(str(song), [])
                    shutil.move(str(song), str(new_path))
                    self.log_status(f"Moved {song.name} to TempDownloads")
                else:
                    # Can't move, tag with empty
                    if song.suffix.lower() == ".mp3":
                        tag_song_with_playlists(str(song), [])
            else:
                # Not moving, tag with empty playlists
                if song.suffix.lower() == ".mp3":
                    tag_song_with_playlists(str(song), [])

    def bulk_search(self):
        term = self.bulk_search_entry.get().strip()
        if not term:
            return
        threading.Thread(target=self._bulk_find_matches, args=(term,)).start()

    def _bulk_find_matches(self, term):
        matches = find_song_matches(term)
        self.root.after(0, self.display_bulk_matches, matches)

    def display_bulk_matches(self, matches):
        self.bulk_matches_listbox.delete(0, tk.END)
        self.bulk_matches_data = matches
        for song in matches:
            self.bulk_matches_listbox.insert(tk.END, song.name)

    def add_selected_bulk(self):
        pl_name = self.bulk_playlist_var.get()
        if not pl_name:
            messagebox.showerror("Error", "Select a playlist first")
            return
        selected = self.bulk_matches_listbox.curselection()
        if not selected:
            return
        chosen = [self.bulk_matches_data[i] for i in selected]
        self.bulk_playlist_path = PLAYLISTS / f"{pl_name}.m3u"
        # Move to AllSongs if needed
        for song in chosen:
            if song.parent == TEMP_DOWNLOADS:
                new_path = ALL_SONGS_PATH / song.name
                if not new_path.exists():
                    shutil.move(str(song), str(new_path))
                    song = new_path
        add_songs_to_playlist(chosen, self.bulk_playlist_path)
        self.bulk_added_count = getattr(self, 'bulk_added_count', 0) + len(chosen)
        self.bulk_added_label.config(text=f"Songs added: {self.bulk_added_count}")
        self.log_status(f"Added {len(chosen)} songs to {self.bulk_playlist_path.stem}")

    def finish_bulk(self):
        self.bulk_added_count = 0
        self.bulk_added_label.config(text="Songs added: 0")
        self.log_status("Bulk add finished")

    def run_auto_clean(self):
        threading.Thread(target=self._cleanup_orphaned_songs).start()

    def _cleanup_orphaned_songs(self):
        if not ALL_SONGS_PATH.exists():
            self.log_status("AllSongs folder not found.")
            return
        moved_count = 0
        for song_path in ALL_SONGS_PATH.glob("*"):
            if song_path.is_file() and is_audio(song_path):
                if not song_playlists(song_path):
                    new_path = TEMP_DOWNLOADS / song_path.name
                    if not new_path.exists():
                        shutil.move(str(song_path), str(new_path))
                        self.log_status(f"Moved {song_path.name} to TempDownloads (no playlists)")
                        moved_count += 1
                    else:
                        self.log_status(f"Skipped {song_path.name} (already exists in TempDownloads)")
        self.log_status(f"Auto clean completed. Moved {moved_count} orphaned songs.")

    def _on_entry_focus_in(self, event):
        if self.url_entry.get() == "Enter URL or search query":
            self.url_entry.delete(0, tk.END)
            self.url_entry.config(foreground="black")

    def _on_entry_focus_out(self, event):
        if self.download_mode.get() == "batch":
            return  # Don't reset placeholder in batch mode
        if not self.url_entry.get():
            self.url_entry.insert(0, "Enter URL or search query")
            self.url_entry.config(foreground="gray")

    def _on_mode_change(self, *args):
        mode = self.download_mode.get()
        if mode == "batch":
            self.input_frame.config(text="")
            self.url_entry.delete(0, tk.END)
            self.url_entry.grid_remove()
            self.current_song_label.grid()
            self.process_button.config(text="Process List")
            self.random_check.pack(side=tk.LEFT, padx=5)
        else:
            self.input_frame.config(text="Input")
            self.url_entry.grid(row=0, column=0, sticky=tk.EW, padx=5, pady=(5,0))
            self.current_song_label.grid_remove()
            self.process_button.config(text="Process")
            self.batch_mode = False
            self.skip_button.pack_forget()
            self.random_check.pack_forget()
        # Clear results and reset progress
        self.results_listbox.delete(0, tk.END)
        self._reset_progress()

    def open_video_link(self, event):
        selected = self.results_listbox.curselection()
        if selected:
            index = selected[0]
            sel = self.search_results[index]
            url = f"https://www.youtube.com/watch?v={sel.get('id')}"
            import webbrowser
            webbrowser.open(url)

    def update_playlist_checks_for_song(self, event=None):
        selected = self.song_matches_listbox.curselection()
        if selected:
            song = self.song_matches_data[selected[0]]
            current_pls = [pl.stem for pl in song_playlists(song)]
            for pl in self.song_changer_playlist_vars:
                self.song_changer_playlist_vars[pl].set(pl in current_pls)

    def open_song_file(self, event):
        selected = self.song_matches_listbox.curselection()
        if selected:
            song = self.song_matches_data[selected[0]]
            import subprocess
            subprocess.run(['explorer', '/select,', str(song)])

    def _on_tab_change(self, event):
        # Clear results and reset progress when switching tabs
        if hasattr(self, 'single_results_listbox'):
            self.single_results_listbox.delete(0, tk.END)
        if hasattr(self, 'batch_results_listbox'):
            self.batch_results_listbox.delete(0, tk.END)
        self._reset_progress()

    def _reset_progress(self):
        self.progress_value = 0
        self.progress_text = "Ready"
        self.percent_label.config(text="0%")
        self._draw_progress()

    def _update_progress(self, percent, text):
        self.progress_value = percent
        self.progress_text = text
        self.percent_label.config(text=f"{percent}%")
        self._draw_progress()

    def _draw_progress(self, event=None):
        self.progress_canvas.delete("all")
        width = self.progress_canvas.winfo_width()
        height = self.progress_canvas.winfo_height()
        if width <= 1:
            return  # Not yet configured

        # Draw background
        self.progress_canvas.create_rectangle(0, 0, width, height, fill=self.secondary_bg, outline='black')

        # Draw progress fill
        fill_width = int(width * self.progress_value / 100)
        self.progress_canvas.create_rectangle(0, 0, fill_width, height, fill=self.progress_fill, outline='')

        # Draw text in the center
        text_x = width // 2
        text_y = height // 2
        self.progress_canvas.create_text(text_x, text_y, text=self.progress_text, anchor='center', fill=self.fg_color, font=('Arial', 10, 'bold'))

    def _get_playlist_cols(self):
        width = self.root.winfo_width()
        if width > 1200:
            return 15
        else:
            return 5

    def _on_window_resize(self, event=None):
        # Only update if column count changed, and debounce with after()
        new_cols = self._get_playlist_cols()
        if new_cols != self.current_playlist_cols:
            self.current_playlist_cols = new_cols
            # Debounce to avoid rapid updates
            if hasattr(self, '_resize_after_id'):
                self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = self.root.after(200, self._update_playlist_grids)

    def _update_playlist_grids(self):
        self.update_playlist_checkbuttons()
        self.update_single_playlist_checkbuttons()
        self.update_batch_playlist_checkbuttons()

    def save_max_concurrent(self):
        global MAX_CONCURRENT
        try:
            MAX_CONCURRENT = int(self.max_concurrent_var.get())
            messagebox.showinfo("Saved", f"Max concurrent set to {MAX_CONCURRENT}")
        except ValueError:
            messagebox.showerror("Error", "Invalid number")

    def save_settings(self):
        global SONGS_FILE, TEMP_DIR, PLAYLISTS_DIR, ALL_SONGS, DEST_ROOT, ALL_SONGS_PATH, TEMP_DOWNLOADS, PLAYLISTS
        SONGS_FILE = self.songs_file_var.get()
        TEMP_DIR = self.temp_dir_var.get()
        PLAYLISTS_DIR = self.playlists_dir_var.get()
        ALL_SONGS = self.all_songs_var.get()
        DEST_ROOT = Path(PLAYLISTS_DIR)
        ALL_SONGS_PATH = DEST_ROOT / "AllSongs"
        TEMP_DOWNLOADS = DEST_ROOT.parent / "TempDownloads"
        PLAYLISTS = DEST_ROOT
        # Create directories if they don't exist
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(PLAYLISTS_DIR, exist_ok=True)
        os.makedirs(ALL_SONGS, exist_ok=True)
        messagebox.showinfo("Saved", "Settings saved successfully")

    def open_songs_file(self):
        import subprocess
        subprocess.run(['notepad', SONGS_FILE])

# Helper functions from original scripts
def is_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS

def list_playlists() -> list[Path]:
    PLAYLISTS.mkdir(parents=True, exist_ok=True)
    return sorted(PLAYLISTS.glob("*.m3u"))

def find_song_matches(term: str):
    all_songs = []
    if ALL_SONGS_PATH.exists():
        all_songs.extend([s for s in ALL_SONGS_PATH.glob("*") if s.is_file() and is_audio(s)])
    if TEMP_DOWNLOADS.exists():
        all_songs.extend([s for s in TEMP_DOWNLOADS.glob("*") if s.is_file() and is_audio(s)])
    names = [s.stem for s in all_songs]

    close = difflib.get_close_matches(term, names, n=15, cutoff=0.3)
    matches = [s for s in all_songs if s.stem in close]

    term_lower = term.lower()
    substring_matches = [s for s in all_songs if term_lower in s.stem.lower()]

    seen = set()
    final = []
    for s in matches + substring_matches:
        if s not in seen:
            seen.add(s)
            final.append(s)
    return final

def song_playlists(song_path: Path) -> list[Path]:
    rel = os.path.relpath(song_path, PLAYLISTS).replace("\\", "/")
    pls = []
    for pl in list_playlists():
        lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
        if rel in lines:
            pls.append(pl)
    return pls

def set_playlists_for_songs(song_paths: list[Path], keep_names: list[str]):
    all_pls = list_playlists()
    chosen = [pl for pl in all_pls if pl.stem in keep_names]

    if keep_names:
        for i, song_path in enumerate(song_paths):
            if song_path.parent == TEMP_DOWNLOADS:
                new_path = ALL_SONGS_PATH / song_path.name
                if not new_path.exists():
                    shutil.move(str(song_path), str(new_path))
                    song_paths[i] = new_path

    for song_path in song_paths:
        rel = os.path.relpath(song_path, PLAYLISTS).replace("\\", "/")

        for pl in all_pls:
            lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
            new_lines = [ln for ln in lines if ln.strip() and ln != rel]
            if lines != new_lines:
                pl.write_text("\n".join(new_lines), encoding="utf-8")

        for pl in chosen:
            lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines() if pl.exists() else []
            if not lines or lines[0] != "#EXTM3U":
                lines.insert(0, "#EXTM3U")
            if rel not in lines:
                lines.append(rel)
                pl.write_text("\n".join(lines), encoding="utf-8")

    for song_path in song_paths:
        if song_path.suffix.lower() == ".mp3" and song_path.exists():
            playlists = [pl.stem for pl in song_playlists(song_path)]
            tag_song_with_playlists(str(song_path), playlists)

    for i, song_path in enumerate(song_paths):
        if song_path.parent == ALL_SONGS_PATH and not song_playlists(song_path):
            new_path = TEMP_DOWNLOADS / song_path.name
            if not new_path.exists():
                shutil.move(str(song_path), str(new_path))
                song_paths[i] = new_path

def delete_song(song_path: Path):
    for pl in song_playlists(song_path):
        lines = pl.read_text(encoding="utf-8", errors="ignore").splitlines()
        rel = os.path.relpath(song_path, PLAYLISTS).replace("\\", "/")
        new_lines = [ln for ln in lines if ln.strip() and ln != rel]
        pl.write_text("\n".join(new_lines), encoding="utf-8")
    if song_path.exists():
        song_path.unlink()

def tag_song_with_playlists(song_path: str, playlists: list[str], thumbnail_data=None, mime=None, uploader=None):
    comment_text = ", ".join(playlists)

    try:
        tags = ID3(song_path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.delall("COMM")
    tags.add(COMM(encoding=3, lang="eng", desc="", text=comment_text))

    if thumbnail_data:
        tags.add(APIC(encoding=3, mime=mime or 'image/jpeg', type=3, desc='Cover', data=thumbnail_data))

    if uploader:
        tags.add(TPE1(encoding=3, text=uploader))

    tags.save(song_path, v2_version=3)

def add_songs_to_playlist(song_paths: list[Path], playlist_path: Path):
    rels = [os.path.relpath(song_path, PLAYLISTS).replace("\\", "/") for song_path in song_paths]
    # Ensure playlist file exists with header
    if not playlist_path.exists():
        playlist_path.write_text("#EXTM3U\n", encoding="utf-8")
    # Append each entry
    for rel in rels:
        with playlist_path.open("a", encoding="utf-8") as f:
            f.write('\n' + rel)

# Download functions adapted
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

async def download_song_gui(entry, playlist_names, log_func, update_func=None):
    url = entry["url"]
    original_input = entry.get("input", url)
    log_func(f"Starting download: {url}")
    if update_func:
        update_func(10, "Fetching video info")

    ydl_opts = {
        "outtmpl": os.path.join(TEMP_DIR, "%(id)s.%(ext)s"),
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
        if update_func:
            update_func(20, "Downloading video")
        info = await loop.run_in_executor(None, run_download, ydl_opts, url)
    except Exception as e:
        error_msg = str(e)
        if "Video unavailable" in error_msg:
            log_func(f"Error: Video is unavailable or private: {url}")
        elif "Unsupported URL" in error_msg:
            log_func(f"Error: Unsupported URL format: {url}")
        elif "ffmpeg" in error_msg.lower():
            log_func(f"Error: Audio conversion failed. Ensure ffmpeg is installed: {url}")
        else:
            log_func(f"Download failed: {error_msg}")
        return

    src = info.get('filepath')
    if not src or not os.path.exists(src):
        # Try expected filename based on id
        vid_id = info.get('id')
        if vid_id:
            expected = os.path.join(TEMP_DIR, f"{vid_id}.mp3")
            if os.path.exists(expected):
                src = expected
            else:
                log_func("Could not locate downloaded file in TempDownloads.")
                return
        else:
            log_func("Could not locate downloaded file in TempDownloads.")
            return

    # Rename file to title if possible
    if src.endswith('.mp3') and info.get('title'):
        title = info['title']
        import re
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        if safe_title and safe_title != os.path.splitext(os.path.basename(src))[0]:
            new_src = os.path.join(TEMP_DIR, f"{safe_title}.mp3")
            shutil.move(src, new_src)
            src = new_src

    if update_func:
        update_func(80, "Converting audio")

    thumbnail_data = None
    mime = None
    if thumbnail_url := info.get('thumbnail'):
        try:
            thumbnail_data, mime = await asyncio.to_thread(download_thumbnail, thumbnail_url)
        except Exception as e:
            log_func(f"Failed to download thumbnail: {e}")
    else:
        log_func("No thumbnail available for this video")

    uploader = info.get('uploader')

    dst = src

    if playlist_names:
        os.makedirs(ALL_SONGS, exist_ok=True)

        base = os.path.basename(src)
        name_no_ext, ext = os.path.splitext(base)
        dst = os.path.join(ALL_SONGS, base)
        i = 2
        while os.path.exists(dst):
            dst = os.path.join(ALL_SONGS, f"{name_no_ext} ({i}){ext}")
            i += 1

        try:
            if update_func:
                update_func(90, "Moving file")
            await asyncio.to_thread(shutil.move, src, dst)
            log_func(f"Moved {os.path.basename(dst)} into AllSongs")
        except Exception as e:
            log_func(f"Error moving file into AllSongs: {e}")
            return

        if update_func:
            update_func(95, "Updating playlists")
        for pl in playlist_names:
            pl_path = os.path.join(PLAYLISTS_DIR, f"{pl}.m3u")
            rel = os.path.relpath(dst, PLAYLISTS_DIR).replace("\\", "/")

            try:
                if not os.path.exists(pl_path):
                    async with aiofiles.open(pl_path, "w", encoding="utf-8") as f:
                        await f.write("#EXTM3U\n")
                else:
                    try:
                        async with aiofiles.open(pl_path, "r", encoding="utf-8") as f:
                            content = await f.read()
                    except UnicodeDecodeError:
                        async with aiofiles.open(pl_path, "r", encoding="cp1252") as f:
                            content = await f.read()
                    existing = content.splitlines()
                    if rel not in existing:
                        if not content.endswith('\n'):
                            content += '\n'
                        content += rel + '\n'
                        async with aiofiles.open(pl_path, "w", encoding="utf-8") as f:
                            await f.write(content)
                log_func(f"Added {os.path.basename(dst)} to {pl}.m3u")
            except Exception as e:
                log_func(f"Error adding to playlist {pl}: {e}")

        if update_func:
            update_func(100, "Tagging file")
        tag_song_with_playlists(dst, playlist_names, thumbnail_data, mime, uploader)

    # Tag MP3 even if no playlists selected (for TempDownloads)
    if not playlist_names:
        tag_song_with_playlists(dst, [], thumbnail_data, mime, uploader)

    await remove_from_txt(original_input)
    log_func(f"Finished download and processing: {os.path.basename(dst)}")
    if update_func:
        update_func(100, "Complete")

async def process_links_gui(log_func):
    try:
        async with aiofiles.open(SONGS_FILE, "r", encoding="utf-8") as f:
            lines = await f.readlines()
    except UnicodeDecodeError:
        async with aiofiles.open(SONGS_FILE, "r", encoding="cp1252") as f:
            lines = await f.readlines()
    except FileNotFoundError:
        log_func("No songs.txt found; nothing to do.")
        return

    links = [l.strip() for l in lines if "http" in l]
    queries = [l.strip() for l in lines if "http" not in l and l.strip()]

    tasks = []
    for url in links:
        title = await asyncio.to_thread(get_title_from_url, url)
        log_func(f"Processing: {title}")
        # For batch, assume no playlists or prompt? For simplicity, no playlists for batch
        playlist_names = []  # Could add GUI for this, but for now empty
        entry = {"url": url, "input": url}
        tasks.append(asyncio.create_task(limit_downloads(entry, playlist_names, log_func)))

    for query in queries:
        results = await search_youtube(query, max_results=5)
        if not results:
            log_func(f"No results for: {query}")
            continue

        # For batch, take first result automatically
        sel = results[0]
        playlist_names = []
        entry = {"url": f"https://www.youtube.com/watch?v={sel.get('id')}", "input": query}
        tasks.append(asyncio.create_task(limit_downloads(entry, playlist_names, log_func)))

    if tasks:
        await asyncio.gather(*tasks)

sem = asyncio.Semaphore(MAX_CONCURRENT)
async def limit_downloads(entry, playlist_names, log_func):
    async with sem:
        await download_song_gui(entry, playlist_names, log_func)

def run_download(ydl_opts, url):
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info

def download_thumbnail(url):
    with urllib.request.urlopen(url) as response:
        data = response.read()
        mime = response.headers.get('content-type', 'image/jpeg')
        return data, mime

def find_downloaded_file_from_info(info):
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

async def search_youtube(query, max_results=5):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, search_youtube_sync, query, max_results)

if __name__ == "__main__":
    root = tk.Tk()
    app = MusicGUI(root)
    root.mainloop()
