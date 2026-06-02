import os
import json
import shutil
from datetime import datetime
from github_provider import GitHubProvider
from game_scanner import GameScanner

class SyncManager:
    def __init__(self, config_path="sync_config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.github = None
        self._init_github()
        self.scanner = GameScanner(
            citra_path=self.config.get("citra_path"),
            gba_saves_path=self.config.get("gba_saves_path"),
            ryujinx_path=self.config.get("ryujinx_path"),
            yuzu_path=self.config.get("yuzu_path"),
            desmume_path=self.config.get("desmume_path"),
            rom_directories=self.config.get("rom_directories", [])
        )

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {
            "github_username": "",
            "github_token": "",
            "github_repo_name": "pokesync-saves",
            "citra_path": "",
            "gba_saves_path": "",
            "ryujinx_path": "",
            "yuzu_path": "",
            "desmume_path": "",
            "rom_directories": []
        }

    def save_config(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=4)

    def _init_github(self):
        if self.config.get("github_username") and self.config.get("github_token"):
            self.github = GitHubProvider(
                self.config["github_username"],
                self.config["github_token"],
                self.config["github_repo_name"]
            )

    def update_config(self, new_config):
        self.config.update(new_config)
        self.save_config()
        self._init_github()
        # Update scanner if paths changed
        self.scanner = GameScanner(
            citra_path=self.config.get("citra_path"),
            gba_saves_path=self.config.get("gba_saves_path"),
            ryujinx_path=self.config.get("ryujinx_path"),
            yuzu_path=self.config.get("yuzu_path"),
            desmume_path=self.config.get("desmume_path"),
            rom_directories=self.config.get("rom_directories", [])
        )

    def get_games(self):
        return self.scanner.scan_all()

    def sync_push(self, game):
        if not self.github:
            return False, "GitHub not configured."

        # Ensure repo exists and is initialized
        success, msg = self.github.ensure_repo_exists()
        if not success: return False, msg

        success, msg = self.github.initialize_local_repo()
        if not success: return False, msg

        # Copy file to local repo
        # Structure: <platform>/<game_id>/main
        platform = game['platform']
        game_id = game['id']
        relative_path = os.path.join(platform, game_id, os.path.basename(game['local_path']))
        dest_path = self.github.get_local_path(relative_path)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            # Create local backup before pushing (using PokeSync style)
            self._create_local_backup(game)
            shutil.copy2(game['local_path'], dest_path)

            # Git push
            return self.github.push(f"Update {platform} save: {game['name']}")
        except Exception as e:
            return False, f"Sync failed: {str(e)}"

    def sync_pull(self, game):
        if not self.github:
            return False, "GitHub not configured."

        success, msg = self.github.pull()
        if not success: return False, msg

        platform = game['platform']
        game_id = game['id']
        relative_path = os.path.join(platform, game_id, os.path.basename(game['local_path']))
        repo_path = self.github.get_local_path(relative_path)

        if not os.path.exists(repo_path):
            return False, "Save not found in GitHub."

        try:
            # Backup current local save before overwriting
            self._create_local_backup(game)
            shutil.copy2(repo_path, game['local_path'])
            return True, f"Pulled {game['name']} from GitHub."
        except Exception as e:
            return False, f"Pull failed: {str(e)}"

    def sync_push_all(self):
        """Pushes all detected game saves to GitHub."""
        if not self.github:
            return False, "GitHub not configured."

        games = self.get_games()
        if not games:
            return True, "No games detected."

        success_count = 0
        for game in games:
            success, _ = self.sync_push(game)
            if success:
                success_count += 1

        return True, f"Successfully synced {success_count}/{len(games)} games to GitHub."

    def _create_local_backup(self, game):
        if os.path.exists(game['local_path']):
            backup_dir = os.path.abspath(os.path.join("backups", game['platform'], game['id']))
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{os.path.basename(game['local_path'])}.bak_{timestamp}"
            shutil.copy2(game['local_path'], os.path.join(backup_dir, backup_name))
