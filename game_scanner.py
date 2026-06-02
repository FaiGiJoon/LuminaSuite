import os
import platform
import glob
import re
from pathlib import Path

class GameScanner:
    def __init__(self, citra_path=None, gba_saves_path=None, ryujinx_path=None, yuzu_path=None, desmume_path=None, rom_directories=None):
        self.citra_path = citra_path or self._get_default_citra_path()
        self.gba_saves_path = gba_saves_path
        self.ryujinx_path = ryujinx_path or self._get_default_ryujinx_path()
        self.yuzu_path = yuzu_path or self._get_default_yuzu_path()
        self.desmume_path = desmume_path or self._get_default_desmume_path()
        self.rom_directories = rom_directories or []

    def _get_default_citra_path(self):
        system = platform.system()
        if system == "Windows":
            return os.path.join(os.environ.get("APPDATA", ""), "Citra")
        elif system == "Darwin":
            return os.path.expanduser("~/Library/Application Support/Citra")
        return os.path.expanduser("~/.local/share/citra-emu")

    def _get_default_ryujinx_path(self):
        system = platform.system()
        if system == "Windows":
            return os.path.join(os.environ.get("APPDATA", ""), "Ryujinx")
        elif system == "Darwin":
            return os.path.expanduser("~/Library/Application Support/Ryujinx")
        return os.path.expanduser("~/.config/Ryujinx")

    def _get_default_yuzu_path(self):
        system = platform.system()
        if system == "Windows":
            return os.path.join(os.environ.get("APPDATA", ""), "yuzu")
        elif system == "Darwin":
            return os.path.expanduser("~/Library/Application Support/yuzu")
        return os.path.expanduser("~/.local/share/yuzu")

    def _get_default_desmume_path(self):
        system = platform.system()
        if system == "Windows":
            # DeSmuME often keeps saves in a 'Battery' subfolder where the .exe is,
            # but modern versions use AppData
            return os.path.join(os.environ.get("APPDATA", ""), "DeSmuME")
        elif system == "Darwin":
            return os.path.expanduser("~/Library/Application Support/DeSmuME")
        return os.path.expanduser("~/.config/desmume")

    def scan_citra(self):
        games = []
        if not self.citra_path or not os.path.exists(self.citra_path):
            return games

        # Logic from PokeSync to find title root
        sdmc_path = os.path.join(self.citra_path, "sdmc", "Nintendo 3DS")
        if not os.path.exists(sdmc_path):
            return games

        title_root = None
        try:
            id1_folders = [f for f in os.listdir(sdmc_path) if os.path.isdir(os.path.join(sdmc_path, f))]
            for id1 in id1_folders:
                id1_path = os.path.join(sdmc_path, id1)
                id2_folders = [f for f in os.listdir(id1_path) if os.path.isdir(os.path.join(id1_path, f))]
                for id2 in id2_folders:
                    title_path = os.path.join(id1_path, id2, "title")
                    if os.path.exists(title_path):
                        title_root = title_path
                        break
                if title_root: break
        except Exception: pass

        if not title_root: return games

        type_folders = ["00040000", "00040002"]
        for type_folder in type_folders:
            base_path = os.path.join(title_root, type_folder)
            if not os.path.exists(base_path): continue

            try:
                for short_id in os.listdir(base_path):
                    save_path = os.path.join(base_path, short_id, "data", "00000001", "main")
                    if os.path.exists(save_path):
                        full_id = (type_folder + short_id).upper()
                        games.append({
                            "platform": "Citra",
                            "name": f"3DS Game {full_id}",
                            "id": full_id,
                            "local_path": save_path
                        })
            except Exception: continue
        return games

    def scan_gba(self):
        games = []
        if not self.gba_saves_path or not os.path.exists(self.gba_saves_path):
            return games

        # GBA saves are usually .sav files
        try:
            for file in os.listdir(self.gba_saves_path):
                if file.lower().endswith(".sav"):
                    game_name = os.path.splitext(file)[0]
                    games.append({
                        "platform": "GBA",
                        "name": game_name,
                        "id": game_name,
                        "local_path": os.path.join(self.gba_saves_path, file)
                    })
        except Exception: pass
        return games

    def scan_desmume(self):
        games = []
        if not self.desmume_path or not os.path.exists(self.desmume_path):
            return games

        # DeSmuME saves are usually .dsv files in a 'Battery' folder or root
        search_paths = [self.desmume_path, os.path.join(self.desmume_path, "Battery")]

        for path in search_paths:
            if not os.path.exists(path): continue
            try:
                for file in os.listdir(path):
                    if file.lower().endswith(".dsv"):
                        game_name = os.path.splitext(file)[0]
                        games.append({
                            "platform": "DeSmuME",
                            "name": game_name,
                            "id": game_name,
                            "local_path": os.path.join(path, file)
                        })
            except Exception: pass
        return games

    def scan_switch(self):
        games = []
        # Ryujinx
        if self.ryujinx_path and os.path.exists(self.ryujinx_path):
            save_root = os.path.join(self.ryujinx_path, "bis", "user", "save")
            if os.path.exists(save_root):
                try:
                    for save_id in os.listdir(save_root):
                        # Each folder is a game ID or user ID
                        # Ryujinx structure: bis/user/save/<save_id>/0/ (0 is usually the main save)
                        save_file = os.path.join(save_root, save_id, "0", "main")
                        if os.path.exists(save_file):
                            games.append({
                                "platform": "Ryujinx",
                                "name": f"Switch Game {save_id}",
                                "id": save_id,
                                "local_path": save_file
                            })
                except Exception: pass

        # Yuzu
        if self.yuzu_path and os.path.exists(self.yuzu_path):
            save_root = os.path.join(self.yuzu_path, "nand", "user", "save", "0000000000000000")
            if os.path.exists(save_root):
                try:
                    # Yuzu structure: nand/user/save/000...000/<title_id_low>/<title_id_high>/
                    # This is more complex, using glob
                    for main_file in glob.glob(os.path.join(save_root, "*", "*", "main")):
                        path_parts = main_file.split(os.sep)
                        # title_id is usually parts of the path
                        title_id = path_parts[-3] + path_parts[-2]
                        games.append({
                            "platform": "Yuzu",
                            "name": f"Switch Game {title_id}",
                            "id": title_id,
                            "local_path": main_file
                        })
                except Exception: pass

        return games

    def _extract_metadata(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        name = os.path.splitext(os.path.basename(file_path))[0]
        game_id = name
        platform = "Unknown"

        try:
            if ext == ".gba":
                platform = "GBA"
                with open(file_path, 'rb') as f:
                    f.seek(0xA0)
                    title_bytes = f.read(12)
                name = title_bytes.split(b'\\x00')[0].decode('ascii', errors='ignore').strip()
                game_id = os.path.splitext(os.path.basename(file_path))[0]
            elif ext == ".nds":
                platform = "DeSmuME"
                with open(file_path, 'rb') as f:
                    title_bytes = f.read(12)
                    f.seek(0x0C)
                    code_bytes = f.read(4)
                name = title_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()
                game_id = code_bytes.decode('ascii', errors='ignore').strip()
            elif ext in [".3ds", ".cia"]:
                platform = "Citra"
                # Basic Title ID extraction from filename if present [TitleID]
                match = re.search(r"\[([0-9A-Fa-f]{16})\]", os.path.basename(file_path))
                if match:
                    game_id = match.group(1).upper()
            elif ext in [".nsp", ".xci", ".nca"]:
                platform = "Switch"
                match = re.search(r"\[([0-9A-Fa-f]{16})\]", os.path.basename(file_path))
                if match:
                    game_id = match.group(1).upper()
        except Exception:
            pass

        return {
            "name": name or os.path.splitext(os.path.basename(file_path))[0],
            "id": game_id,
            "platform": platform,
            "rom_path": str(file_path)
        }

    def scan_roms(self):
        roms = []
        extensions = {".gba", ".nds", ".3ds", ".cia", ".nsp", ".xci", ".nca"}
        for directory in self.rom_directories:
            if not os.path.exists(directory):
                continue
            for root, _, files in os.walk(directory):
                for file in files:
                    if os.path.splitext(file)[1].lower() in extensions:
                        rom_path = os.path.join(root, file)
                        roms.append(self._extract_metadata(rom_path))
        return roms

    def scan_all(self):
        saves = self.scan_citra() + self.scan_gba() + self.scan_switch() + self.scan_desmume()
        roms = self.scan_roms()

        collection = {}

        # Process Saves
        for s in saves:
            key = (s['platform'], s['id'])
            collection[key] = {
                "name": s['name'],
                "id": s['id'],
                "platform": s['platform'],
                "save_path": s['local_path'],
                "rom_path": None,
                "status": "Save Only"
            }

        # Process ROMs and Map
        for r in roms:
            # Switch ROMs might be Yuzu or Ryujinx
            platforms_to_check = [r['platform']]
            if r['platform'] == "Switch":
                platforms_to_check = ["Ryujinx", "Yuzu"]

            mapped = False
            for p in platforms_to_check:
                key = (p, r['id'])
                if key in collection:
                    collection[key]["rom_path"] = r['rom_path']
                    collection[key]["status"] = "Ready"
                    # Prefer ROM-extracted name if it's better
                    if not collection[key]["name"].startswith(r['platform']):
                         collection[key]["name"] = r['name']
                    mapped = True
                    break

            if not mapped:
                key = (r['platform'], r['id'])
                collection[key] = {
                    "name": r['name'],
                    "id": r['id'],
                    "platform": r['platform'],
                    "save_path": None,
                    "rom_path": r['rom_path'],
                    "status": "Not Started"
                }

        return list(collection.values())
