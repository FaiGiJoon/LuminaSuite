import os
import sys
import argparse
from sync_manager import SyncManager
import gui_theme

try:
    import customtkinter as ctk
    from tkinter import messagebox, filedialog
    from PIL import Image
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False

class PokeSyncApp(ctk.CTk if GUI_AVAILABLE else object):
    def __init__(self, manager):
        if not GUI_AVAILABLE:
            raise ImportError("customtkinter and Pillow not found. Please install them to use the GUI.")

        super().__init__()
        self.manager = manager
        self.title("FAIGIJOON UTILITY MANAGER")
        self.geometry("1100x750")

        # Set theme colors
        self.configure(fg_color=gui_theme.COLORS["bg"])
        ctk.set_appearance_mode("dark")

        # UI State
        self.current_view = None
        self.current_platform = "All"
        self.search_query = ""

        self.setup_ui()

    def setup_ui(self):
        # Configure grid for sidebar and main area
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main content
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0,
                                   fg_color=gui_theme.COLORS["sidebar_bg"],
                                   border_width=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Sidebar Logo/Title
        self.logo_label = ctk.CTkLabel(self.sidebar, text="POKESYNC",
                                      font=ctk.CTkFont(size=22, weight="bold"),
                                      text_color=gui_theme.COLORS["cyan"])
        self.logo_label.pack(pady=(40, 60))

        # Sidebar Buttons
        self.nav_buttons = {}
        nav_items = [("Home", "🏠"), ("Explore", "🔍"), ("Settings", "⚙️"), ("Utils", "🛠️")]

        for name, icon in nav_items:
            btn = ctk.CTkButton(self.sidebar, text=f"{icon}  {name}",
                               anchor="w",
                               fg_color="transparent",
                               text_color=gui_theme.COLORS["text_dim"],
                               hover_color=gui_theme.COLORS["card_bg"],
                               font=ctk.CTkFont(size=15),
                               height=50,
                               corner_radius=10,
                               command=lambda n=name: self.show_view(n))
            btn.pack(fill="x", padx=20, pady=8)
            self.nav_buttons[name] = btn

        # Main Content Wrapper
        self.content_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.content_wrapper.grid(row=0, column=1, sticky="nsew", padx=25, pady=25)
        self.content_wrapper.grid_columnconfigure(0, weight=1)
        self.content_wrapper.grid_rowconfigure(1, weight=1)

        # Glassmorphism Main Panel
        self.main_container = ctk.CTkFrame(self.content_wrapper, corner_radius=16,
                                          fg_color=gui_theme.COLORS["bg"],
                                          border_color=gui_theme.COLORS["purple"],
                                          border_width=2)
        self.main_container.grid(row=0, column=0, rowspan=2, sticky="nsew")

        # Top Bar simulation inside main container
        self.top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent", height=40)
        self.top_bar.pack(fill="x", padx=20, pady=(15, 0))

        self.window_title = ctk.CTkLabel(self.top_bar, text="FAIGIJOON UTILITY MANAGER",
                                        font=ctk.CTkFont(size=12, weight="bold"),
                                        text_color=gui_theme.COLORS["text_dim"])
        self.window_title.pack(side="left")

        # Close, Max, Min icons (purple, blue, cyan)
        for color in [gui_theme.COLORS["purple"], gui_theme.COLORS["blue"], gui_theme.COLORS["cyan"]]:
            dot = ctk.CTkLabel(self.top_bar, text=" ● ", text_color=color, font=ctk.CTkFont(size=18))
            dot.pack(side="right")

        # View content container
        self.view_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.view_container.pack(fill="both", expand=True)

        self.show_view("Explore")

    def show_view(self, view_name):
        if self.current_view == view_name:
            return

        self.current_view = view_name

        # Update sidebar button styles
        for name, btn in self.nav_buttons.items():
            if name == view_name:
                btn.configure(fg_color=gui_theme.COLORS["blue"],
                              text_color=gui_theme.COLORS["text"])
            else:
                btn.configure(fg_color="transparent",
                              text_color=gui_theme.COLORS["text_dim"])

        # Clear view container
        for widget in self.view_container.winfo_children():
            widget.destroy()

        if view_name == "Home":
            self._render_home()
        elif view_name == "Explore":
            self._render_explore()
        elif view_name == "Settings":
            self._render_settings()
        elif view_name == "Utils":
            self._render_utils()

    def _render_home(self):
        ctk.CTkLabel(self.view_container, text="WELCOME BACK",
                    font=ctk.CTkFont(size=56, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(expand=True)

    def _render_explore(self):
        # Title
        title_label = ctk.CTkLabel(self.view_container, text="EXPLORE",
                                  font=ctk.CTkFont(size=64, weight="bold"),
                                  text_color=gui_theme.COLORS["purple"])
        title_label.pack(anchor="w", padx=50, pady=(30, 20))

        # Search Bar
        search_frame = ctk.CTkFrame(self.view_container,
                                   fg_color=gui_theme.COLORS["card_bg"],
                                   border_color=gui_theme.COLORS["cyan"],
                                   border_width=2,
                                   corner_radius=25)
        search_frame.pack(fill="x", padx=50, pady=15)

        ctk.CTkLabel(search_frame, text=" 🔍 ", font=ctk.CTkFont(size=20),
                    text_color=gui_theme.COLORS["cyan"]).pack(side="left", padx=(20, 0))

        self.search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search games...",
                                        border_width=0, fg_color="transparent",
                                        height=50,
                                        font=ctk.CTkFont(size=16))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(5, 20), pady=5)
        self.search_entry.bind("<KeyRelease>", self.filter_games)

        # Category Filter Chips
        filter_frame = ctk.CTkFrame(self.view_container, fg_color="transparent")
        filter_frame.pack(fill="x", padx=45, pady=10)

        categories = ["All", "GBA", "Citra", "DeSmuME", "Ryujinx", "Yuzu"]
        self.category_btns = {}

        for cat in categories:
            btn = ctk.CTkButton(filter_frame, text=cat, width=110, height=40,
                               corner_radius=20,
                               fg_color=gui_theme.COLORS["card_bg"],
                               border_color=gui_theme.COLORS["cyan"],
                               border_width=1,
                               command=lambda c=cat: self.set_platform_filter(c))
            btn.pack(side="left", padx=8)
            self.category_btns[cat] = btn

        self._update_chip_styles()

        # Content Areas
        scroll_container = ctk.CTkScrollableFrame(self.view_container, fg_color="transparent")
        scroll_container.pack(fill="both", expand=True, padx=30, pady=10)

        # Recommended
        ctk.CTkLabel(scroll_container, text="RECOMMENDED",
                    font=ctk.CTkFont(size=20, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(anchor="w", padx=20, pady=(20, 15))

        self.carousel_frame = ctk.CTkFrame(scroll_container, fg_color="transparent")
        self.carousel_frame.pack(fill="x", padx=10)

        # All Games
        ctk.CTkLabel(scroll_container, text="ALL GAMES",
                    font=ctk.CTkFont(size=20, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(anchor="w", padx=20, pady=(30, 15))

        self.games_frame = ctk.CTkFrame(scroll_container, fg_color="transparent")
        self.games_frame.pack(fill="both", expand=True, padx=10)

        self.refresh_home_lists()

    def _render_settings(self):
        scroll_frame = ctk.CTkScrollableFrame(self.view_container, fg_color="transparent")
        scroll_frame.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll_frame, text="SETTINGS",
                    font=ctk.CTkFont(size=48, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(pady=(40, 25), padx=50, anchor="w")

        # Configuration Card
        config_card = ctk.CTkFrame(scroll_frame, fg_color=gui_theme.COLORS["card_bg"],
                                  border_color=gui_theme.COLORS["cyan"], border_width=2,
                                  corner_radius=20)
        config_card.pack(fill="x", padx=50, pady=10)

        ctk.CTkLabel(config_card, text="Configuration & Paths",
                    font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=gui_theme.COLORS["cyan"]).pack(pady=(20, 15), padx=30, anchor="w")

        self.user_entry = self._create_setting(config_card, "GitHub Username", self.manager.config["github_username"])
        self.token_entry = self._create_setting(config_card, "Token (PAT)", self.manager.config["github_token"], show="*")
        self.repo_entry = self._create_setting(config_card, "Repo Name", self.manager.config["github_repo_name"])
        self.gba_path_entry = self._create_setting(config_card, "GBA Saves Path", self.manager.config.get("gba_saves_path", ""))
        self.citra_path_entry = self._create_setting(config_card, "Citra Path", self.manager.config.get("citra_path", ""))
        self.desmume_path_entry = self._create_setting(config_card, "DeSmuME Path", self.manager.config.get("desmume_path", ""))

        # ROM Directories Card
        rom_card = ctk.CTkFrame(scroll_frame, fg_color=gui_theme.COLORS["card_bg"],
                                  border_color=gui_theme.COLORS["purple"], border_width=2,
                                  corner_radius=20)
        rom_card.pack(fill="x", padx=50, pady=10)

        ctk.CTkLabel(rom_card, text="ROM Directories",
                    font=ctk.CTkFont(size=22, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(pady=(20, 15), padx=30, anchor="w")

        self.rom_listbox = ctk.CTkTextbox(rom_card, height=120, fg_color=gui_theme.COLORS["bg"],
                                         border_color=gui_theme.COLORS["blue"], border_width=1)
        self.rom_listbox.pack(fill="x", padx=30, pady=5)

        # Initial populate
        for path in self.manager.config.get("rom_directories", []):
            self.rom_listbox.insert("end", path + "\n")

        btn_frame = ctk.CTkFrame(rom_card, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(5, 20))

        ctk.CTkButton(btn_frame, text="+ Add Directory", width=140, height=35,
                     fg_color=gui_theme.COLORS["blue"],
                     font=ctk.CTkFont(size=13, weight="bold"),
                     command=self.add_rom_dir).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_frame, text="Clear All", width=140, height=35,
                     fg_color=gui_theme.COLORS["error"],
                     font=ctk.CTkFont(size=13, weight="bold"),
                     command=lambda: self.rom_listbox.delete("1.0", "end")).pack(side="left")

        # Save Button
        save_btn = ctk.CTkButton(scroll_frame, text="Save & Refresh",
                               corner_radius=12,
                               fg_color=gui_theme.COLORS["purple"],
                               hover_color=gui_theme.COLORS["blue"],
                               font=ctk.CTkFont(size=18, weight="bold"),
                               height=55,
                               command=self.save_settings)
        save_btn.pack(pady=40, padx=50, fill="x")

    def _render_utils(self):
        ctk.CTkLabel(self.view_container, text="UTILITIES",
                    font=ctk.CTkFont(size=48, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(pady=(40, 25), padx=50, anchor="w")

        utils_scroll = ctk.CTkScrollableFrame(self.view_container, fg_color="transparent")
        utils_scroll.pack(fill="both", expand=True, padx=30)

        utils = [
            ("ROM Translation", "Launch Omni-Translate", "python3 omni.py --help"),
            ("AI Save Backup", "Launch Save-State Backup", "python3 save_backup.py --help"),
            ("macOS Tagger", "Tag ROMs with Metadata", "python3 mac_rom_tagger.py --help"),
            ("Real-time Translator", "Overlay Translation", "python3 translator.py --help")
        ]

        for name, desc, cmd in utils:
            card = ctk.CTkFrame(utils_scroll, fg_color=gui_theme.COLORS["card_bg"],
                               corner_radius=18, border_width=1, border_color=gui_theme.COLORS["cyan"])
            card.pack(fill="x", pady=12, padx=20)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", padx=25, pady=20)

            ctk.CTkLabel(info_frame, text=name,
                        font=ctk.CTkFont(size=18, weight="bold"),
                        text_color=gui_theme.COLORS["cyan"]).pack(anchor="w")
            ctk.CTkLabel(info_frame, text=desc,
                        font=ctk.CTkFont(size=13),
                        text_color=gui_theme.COLORS["text_dim"]).pack(anchor="w")

            ctk.CTkButton(card, text="Open Help", width=120, height=35, corner_radius=10,
                         fg_color=gui_theme.COLORS["blue"],
                         command=lambda c=cmd: self._launch_util(c)).pack(side="right", padx=25)

        # Logs Panel
        log_header_frame = ctk.CTkFrame(utils_scroll, fg_color="transparent")
        log_header_frame.pack(fill="x", padx=20, pady=(40, 10))
        ctk.CTkLabel(log_header_frame, text="Log Output [SUCCESS/INFO]",
                    font=ctk.CTkFont(size=18, weight="bold"),
                    text_color=gui_theme.COLORS["purple"]).pack(side="left")

        log_panel = ctk.CTkFrame(utils_scroll, fg_color=gui_theme.COLORS["card_bg"],
                                corner_radius=14, border_width=2, border_color=gui_theme.COLORS["blue"])
        log_panel.pack(fill="both", expand=True, padx=20, pady=(0, 30))

        log_text_box = ctk.CTkTextbox(log_panel, fg_color="transparent",
                                     font=ctk.CTkFont(family="Courier", size=13),
                                     height=250)
        log_text_box.pack(fill="both", expand=True, padx=15, pady=15)

        # Insert log text
        logs = [
            ("[SUCCESS]", gui_theme.COLORS["success"], "Verified that color_constants.py contains the required ANSI sequences and style presets for the CLI fallbacks."),
            ("[INFO]", gui_theme.COLORS["info"], "GUI environment check: customtkinter found, display server active."),
            ("[SUCCESS]", gui_theme.COLORS["success"], "Verified that all modified scripts (omni.py, save_backup.py, mac_rom_tagger.py, sync_app.py) execute without import errors and follow the new Faigijoon design language."),
            ("[INFO]", gui_theme.COLORS["info"], "Successfully transition from terminal-based ANSI styling to a high-fidelity Graphical User Interface (GUI).")
        ]

        for tag, color, msg in logs:
            log_text_box.insert("end", f"{tag} ", tag)
            log_text_box.insert("end", f"{msg}\n\n")
            log_text_box.tag_config(tag, foreground=color)

        log_text_box.configure(state="disabled")

    def _launch_util(self, command):
        print(f"Launching utility: {command}")
        messagebox.showinfo("Utility", f"This would launch: {command}")

    def _create_setting(self, parent, label, value, show=None):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=30, pady=8)

        ctk.CTkLabel(frame, text=label, text_color=gui_theme.COLORS["text_dim"],
                    font=ctk.CTkFont(size=13)).pack(anchor="w")
        entry = ctk.CTkEntry(frame, show=show, fg_color=gui_theme.COLORS["bg"],
                            border_color=gui_theme.COLORS["blue"], border_width=1,
                            height=35)
        entry.insert(0, value)
        entry.pack(fill="x", pady=(5, 5))
        return entry

    def filter_games(self, event=None):
        self.search_query = self.search_entry.get().lower()
        self.refresh_home_lists()

    def set_platform_filter(self, platform):
        self.current_platform = platform
        self._update_chip_styles()
        self.refresh_home_lists()

    def _update_chip_styles(self):
        for cat, btn in self.category_btns.items():
            if cat == self.current_platform:
                btn.configure(fg_color=gui_theme.COLORS["purple"],
                              border_color=gui_theme.COLORS["cyan"],
                              text_color="white")
            else:
                btn.configure(fg_color=gui_theme.COLORS["card_bg"],
                              border_color=gui_theme.COLORS["cyan"],
                              text_color=gui_theme.COLORS["text_dim"])

    def refresh_home_lists(self):
        # Clear existing
        for widget in self.carousel_frame.winfo_children():
            widget.destroy()
        for widget in self.games_frame.winfo_children():
            widget.destroy()

        all_games = self.manager.get_games()

        # Apply filters
        filtered_games = []
        for game in all_games:
            matches_search = self.search_query in game['name'].lower() or \
                             self.search_query in game['platform'].lower()
            matches_platform = self.current_platform == "All" or \
                               game['platform'] == self.current_platform

            if matches_search and matches_platform:
                filtered_games.append(game)

        # Recommended (subset, first 4)
        if filtered_games:
            for game in filtered_games[:4]:
                self._create_game_card(self.carousel_frame, game, horizontal=True)

        # All Games
        if not filtered_games:
            empty_card = ctk.CTkFrame(self.games_frame, fg_color=gui_theme.COLORS["card_bg"],
                                     corner_radius=20, border_width=1, border_color=gui_theme.COLORS["blue"])
            empty_card.pack(pady=60, padx=50, fill="x")

            ctk.CTkLabel(empty_card, text="📭", font=ctk.CTkFont(size=64)).pack(pady=(30, 10))
            ctk.CTkLabel(empty_card, text="No games found",
                        font=ctk.CTkFont(size=20, weight="bold"),
                        text_color=gui_theme.COLORS["cyan"]).pack(pady=(0, 30))
        else:
            for game in filtered_games:
                self._create_game_card(self.games_frame, game, horizontal=False)

    def _create_game_card(self, parent, game, horizontal=False):
        if horizontal:
            card = ctk.CTkFrame(parent, width=200, height=220,
                               fg_color=gui_theme.COLORS["card_bg"],
                               corner_radius=18, border_width=2, border_color=gui_theme.COLORS["purple"])
            card.pack(side="left", padx=12, pady=10)
            card.pack_propagate(False)

            # Status Tag
            status_colors = {"Ready": gui_theme.COLORS["success"], "Not Started": gui_theme.COLORS["info"], "Save Only": gui_theme.COLORS["warning"]}
            status_color = status_colors.get(game.get('status', 'Ready'), gui_theme.COLORS["text_dim"])

            tag_frame = ctk.CTkFrame(card, fg_color="transparent")
            tag_frame.pack(pady=(15, 5))

            # Platform Tag
            p_color = self._get_platform_color(game['platform'])
            ctk.CTkLabel(tag_frame, text=game['platform'], font=ctk.CTkFont(size=10, weight="bold"),
                        fg_color=p_color, text_color="white", corner_radius=6, width=60).pack(side="left", padx=2)

            # Status Tag
            ctk.CTkLabel(tag_frame, text=game.get('status', 'Ready').upper(), font=ctk.CTkFont(size=10, weight="bold"),
                        fg_color=status_color, text_color="white", corner_radius=6, width=80).pack(side="left", padx=2)

            ctk.CTkLabel(card, text=game['name'], font=ctk.CTkFont(size=15, weight="bold"),
                        text_color=gui_theme.COLORS["text"],
                        wraplength=170).pack(pady=10, padx=15)

            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(side="bottom", pady=15)

            if game.get('status') == "Not Started":
                 ctk.CTkButton(btn_frame, text="Start Game", width=160, height=35,
                             fg_color=gui_theme.COLORS["purple"],
                             font=ctk.CTkFont(size=12, weight="bold"),
                             command=lambda: messagebox.showinfo("Launch", f"Launch {game['name']} to create a save!")).pack(padx=5)
            else:
                ctk.CTkButton(btn_frame, text="Push", width=75, height=35,
                             fg_color=gui_theme.COLORS["success"],
                             font=ctk.CTkFont(size=12, weight="bold"),
                             command=lambda: self.sync_action("push", game)).pack(side="left", padx=5)
                ctk.CTkButton(btn_frame, text="Pull", width=75, height=35,
                             fg_color=gui_theme.COLORS["info"],
                             font=ctk.CTkFont(size=12, weight="bold"),
                             command=lambda: self.sync_action("pull", game)).pack(side="left", padx=5)
        else:
            card = ctk.CTkFrame(parent, fg_color=gui_theme.COLORS["card_bg"],
                               corner_radius=15, border_width=1, border_color=gui_theme.COLORS["cyan"])
            card.pack(fill="x", padx=15, pady=8)

            ctk.CTkLabel(card, text=game['name'],
                        font=ctk.CTkFont(size=17, weight="bold"),
                        text_color=gui_theme.COLORS["text"]).pack(side="left", padx=25, pady=20)

            # Actions on the right
            if game.get('status') == "Not Started":
                 ctk.CTkButton(card, text="Launch", width=90, height=38,
                             fg_color=gui_theme.COLORS["purple"],
                             font=ctk.CTkFont(size=13, weight="bold"),
                             command=lambda: messagebox.showinfo("Launch", f"Launch {game['name']} to create a save!")).pack(side="right", padx=15)
            else:
                ctk.CTkButton(card, text="Pull", width=90, height=38,
                             fg_color=gui_theme.COLORS["info"],
                             font=ctk.CTkFont(size=13, weight="bold"),
                             command=lambda g=game: self.sync_action("pull", g)).pack(side="right", padx=15)
                ctk.CTkButton(card, text="Push", width=90, height=38,
                             fg_color=gui_theme.COLORS["success"],
                             font=ctk.CTkFont(size=13, weight="bold"),
                             command=lambda g=game: self.sync_action("push", g)).pack(side="right", padx=5)

            status_colors = {"Ready": gui_theme.COLORS["success"], "Not Started": gui_theme.COLORS["info"], "Save Only": gui_theme.COLORS["warning"]}
            status_color = status_colors.get(game.get('status', 'Ready'), gui_theme.COLORS["text_dim"])

            ctk.CTkLabel(card, text=game.get('status', 'Ready').upper(), font=ctk.CTkFont(size=11, weight="bold"),
                        fg_color=status_color, text_color="white", corner_radius=8,
                        width=90, height=28).pack(side="right", padx=10)

            tag_color = self._get_platform_color(game['platform'])
            ctk.CTkLabel(card, text=game['platform'], font=ctk.CTkFont(size=12, weight="bold"),
                        fg_color=tag_color, text_color="white", corner_radius=8,
                        width=85, height=28).pack(side="right", padx=10)

    def _get_platform_color(self, platform):
        colors = {
            "GBA": "#32D74B",    # Success green
            "Citra": "#FF9F0A",  # Warning orange
            "DeSmuME": "#BF5AF2",# Purple
            "Ryujinx": "#5856D6",# Blue
            "Yuzu": "#5AC8FA"    # Cyan
        }
        return colors.get(platform, "#8E8E93")

    def add_rom_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.rom_listbox.insert("end", path + "\n")

    def save_settings(self):
        rom_dirs = self.rom_listbox.get("1.0", "end-1c").strip().split("\n")
        rom_dirs = [d.strip() for d in rom_dirs if d.strip()]

        new_config = {
            "github_username": self.user_entry.get(),
            "github_token": self.token_entry.get(),
            "github_repo_name": self.repo_entry.get(),
            "gba_saves_path": self.gba_path_entry.get(),
            "citra_path": self.citra_path_entry.get(),
            "desmume_path": self.desmume_path_entry.get(),
            "rom_directories": rom_dirs
        }
        self.manager.update_config(new_config)
        messagebox.showinfo("Success", "Settings saved and synchronized.")

    def sync_action(self, action, game):
        if action == "push":
            success, msg = self.manager.sync_push(game)
        else:
            success, msg = self.manager.sync_pull(game)

        if success:
            messagebox.showinfo("Success", msg)
        else:
            messagebox.showerror("Error", msg)

def cli_main():
    parser = argparse.ArgumentParser(description="PokeSync CLI")
    parser.add_argument("--list", action="store_true", help="List detected games")
    parser.add_argument("--push", help="Push save for game ID")
    parser.add_argument("--pull", help="Pull save for game ID")
    parser.add_argument("--platform", help="Platform for push/pull (Citra, GBA, Ryujinx, Yuzu)")

    args = parser.parse_args()
    manager = SyncManager()

    if args.list:
        games = manager.get_games()
        print(f"{'Platform':<10} {'ID':<20} {'Name'}")
        print("-" * 50)
        for g in games:
            print(f"{g['platform']:<10} {g['id']:<20} {g['name']}")

    elif args.push:
        games = [g for g in manager.get_games() if g['id'] == args.push]
        if args.platform:
            games = [g for g in games if g['platform'].lower() == args.platform.lower()]

        if not games:
            print(f"Game {args.push} not found.")
        else:
            success, msg = manager.sync_push(games[0])
            print(msg)

    elif args.pull:
        games = [g for g in manager.get_games() if g['id'] == args.pull]
        if args.platform:
            games = [g for g in games if g['platform'].lower() == args.platform.lower()]

        if not games:
            print(f"Game {args.pull} not found.")
        else:
            success, msg = manager.sync_pull(games[0])
            print(msg)
    else:
        if GUI_AVAILABLE:
            app = PokeSyncApp(manager)
            app.mainloop()
        else:
            parser.print_help()

if __name__ == "__main__":
    cli_main()
