import os
import shutil
import time
import sys
import re
import json
import subprocess
from datetime import datetime
from color_constants import SUCCESS, INFO, WARNING, ERROR, HEADER, RESET
try:
    import psutil
except ImportError:
    psutil = None

# AI components
AI_CAPTIONER = None
def load_ai():
    global AI_CAPTIONER
    if AI_CAPTIONER is None:
        try:
            from transformers import pipeline
            # Use a small, efficient model
            AI_CAPTIONER = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
            print(f"{SUCCESS} AI Scene Recognition model loaded.")
        except Exception as e:
            print(f"{WARNING} AI model loading failed (will use placeholder): {e}")

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Pattern to match backup files: name_YYYYMMDD_HHMMSS_ffffff.ext
BACKUP_PATTERN = re.compile(r".*_\d{8}_\d{6}_\d{6}\..*")
METADATA_FILE = "metadata.json"

class SaveBackupHandler(FileSystemEventHandler):
    def __init__(self, backup_dir, extensions=None, retention_days=7, cpu_threshold=60, use_delta=False, git_sync=False):
        self.backup_dir = os.path.abspath(backup_dir)
        self.extensions = extensions
        self.retention_days = retention_days
        self.cpu_threshold = cpu_threshold
        self.use_delta = use_delta
        self.git_sync = git_sync
        self.last_prune_time = 0
        self.last_backup_events = {} # {file_path: timestamp}
        self.metadata_path = os.path.join(self.backup_dir, METADATA_FILE)
        self.metadata = self.load_metadata()

        if self.git_sync:
            try:
                from sync_manager import SyncManager
                self.sync_manager = SyncManager()
                print("Git Sync enabled for Milestone backups.")
            except Exception as e:
                print(f"Failed to initialize SyncManager for Git Sync: {e}")
                self.git_sync = False

    def load_metadata(self):
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"{ERROR} Error loading metadata: {e}")
        return {}

    def save_metadata(self):
        try:
            with open(self.metadata_path, 'w') as f:
                json.dump(self.metadata, f, indent=4)
        except Exception as e:
            print(f"{ERROR} Error saving metadata: {e}")

    def on_modified(self, event):
        if not event.is_directory:
            self.handle_event(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.handle_event(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.handle_event(event.dest_path)

    def handle_event(self, file_path):
        file_path = os.path.abspath(file_path)
        
        # Prevent infinite loop: skip if file is inside the backup directory
        if file_path.startswith(self.backup_dir):
            return

        if self.should_backup(file_path):
            # Debounce: skip if we recently backed up this file
            current_time = time.time()
            last_time = self.last_backup_events.get(file_path, 0)
            if current_time - last_time < 2: # 2 second debounce
                return

            # Performance Throttling
            if psutil:
                while psutil.cpu_percent(interval=1) > self.cpu_threshold:
                    print(f"{WARNING} System load high, delaying backup for {os.path.basename(file_path)}...")
                    time.sleep(5)
            
            backup_path = copy_with_timestamp(file_path, self.backup_dir, use_delta=self.use_delta, metadata=self.metadata)
            if backup_path:
                self.last_backup_events[file_path] = current_time

                # If this was a milestone, trigger Git Sync if enabled
                if self.git_sync and self.metadata.get(os.path.basename(backup_path), {}).get("milestone"):
                    print(f"Milestone detected for {os.path.basename(file_path)}. Triggering Git Sync...")
                    # We need to find the game in sync manager
                    games = self.sync_manager.get_games()
                    game = next((g for g in games if os.path.abspath(g['local_path']) == file_path), None)
                    if game:
                        success, msg = self.sync_manager.sync_push(game)
                        print(f"Git Sync Status: {msg}")
                    else:
                        print("File not recognized by PokeSync. Skipping Git Sync.")

                self.save_metadata()
                self.periodic_prune()

    def should_backup(self, file_path):
        if self.extensions:
            return any(file_path.endswith(ext) for ext in self.extensions)
        return True

    def periodic_prune(self):
        # Prune at most once per hour to avoid excessive overhead
        current_time = time.time()
        if current_time - self.last_prune_time > 3600:
            prune_backups(self.backup_dir, self.retention_days, metadata=self.metadata)
            self.save_metadata()
            self.last_prune_time = current_time

def recognize_scene(source_file):
    """
    AI-powered scene recognition using a vision model.
    Captures context from a companion screenshot if available.
    """
    screenshot_path = os.path.splitext(source_file)[0] + ".png"
    if os.path.exists(screenshot_path):
        if AI_CAPTIONER:
            try:
                from PIL import Image
                img = Image.open(screenshot_path).convert('RGB')
                result = AI_CAPTIONER(img)
                if result and 'generated_text' in result[0]:
                    return result[0]['generated_text']
            except Exception as e:
                print(f"{ERROR} Error during AI scene recognition: {e}")
        return f"Scene with screenshot {os.path.basename(screenshot_path)}"
    return "No screenshot available"

def calculate_importance(source_file, last_backup_path):
    """
    Calculates importance score based on size difference.
    In a real scenario, this could be more complex (e.g., binary delta).
    """
    if not last_backup_path or not os.path.exists(last_backup_path):
        return 1.0 # Initial backup is important

    try:
        current_size = os.path.getsize(source_file)
        last_size = os.path.getsize(last_backup_path)
        # Simplified importance: absolute relative change in size
        if last_size == 0:
            return 1.0
        delta = abs(current_size - last_size) / last_size
        return delta
    except Exception:
        return 0.0

def copy_with_timestamp(source_file, backup_dir, use_delta=False, metadata=None):
    """
    Copies source_file to backup_dir with a high-resolution timestamp.
    If use_delta is True, it attempts to store a delta instead of a full copy.
    """
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    filename = os.path.basename(source_file)
    name, ext = os.path.splitext(filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # Milestone logic: check importance relative to the last backup (any type)
    is_milestone = False
    last_any_backup = None
    if metadata:
        backups = [b for b in metadata.values() if b.get("original_filename") == filename]
        if backups:
            last_any_backup = sorted(backups, key=lambda x: x["timestamp"], reverse=True)[0]

    # Scene recognition
    label = recognize_scene(source_file)

    if last_any_backup:
        last_path = os.path.join(backup_dir, last_any_backup["backup_filename"])
        importance = calculate_importance(source_file, last_path)
        if importance > 0.1: # Threshold for milestone
            is_milestone = True
            print(f"{INFO} Significant change detected (score: {importance:.2f}). Flagging as Milestone.")
    else:
        is_milestone = True # First backup is always a milestone

    # Check if we should use delta
    last_full_backup = None
    if use_delta and metadata:
        # Find the latest full backup for this specific file
        backups = [b for b in metadata.values() if b.get("original_filename") == filename and b.get("type") == "full"]
        if backups:
            last_full_backup = sorted(backups, key=lambda x: x["timestamp"], reverse=True)[0]

    if last_full_backup:
        backup_filename = f"{name}_{timestamp}{ext}.vcdiff"
        backup_path = os.path.join(backup_dir, backup_filename)
        source_full_path = os.path.join(backup_dir, last_full_backup["backup_filename"])

        try:
            cmd = ["xdelta3", "-e", "-s", source_full_path, source_file, backup_path]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"{SUCCESS} Delta backup created: {filename} -> {backup_filename}")
            if metadata is not None:
                metadata[backup_filename] = {
                    "backup_filename": backup_filename,
                    "original_filename": filename,
                    "timestamp": timestamp,
                    "type": "delta",
                    "parent": last_full_backup["backup_filename"],
                    "milestone": is_milestone,
                    "label": label
                }
            return backup_path
        except subprocess.CalledProcessError as e:
            print(f"{WARNING} Error creating delta backup (falling back to full): {e}")
            # Fallback to full backup below

    # Full backup logic
    backup_filename = f"{name}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # Using shutil.copy instead of copy2 to update mtime to backup time
        shutil.copy(source_file, backup_path)
        print(f"{SUCCESS} Backed up: {filename} -> {backup_filename}")
        if metadata is not None:
            metadata[backup_filename] = {
                "backup_filename": backup_filename,
                "original_filename": filename,
                "timestamp": timestamp,
                "type": "full",
                "milestone": is_milestone,
                "label": label
            }
        return backup_path
    except Exception as e:
        print(f"Error backing up {filename}: {e}")
        return None

def prune_backups(backup_dir, days=7, metadata=None):
    """
    Deletes files in backup_dir older than 'days' days, unless they are milestones.
    """
    if not os.path.exists(backup_dir):
        return

    now = time.time()
    cutoff = now - (days * 86400)
    
    for filename in os.listdir(backup_dir):
        if not BACKUP_PATTERN.match(filename):
            continue

        # Check metadata for milestone status
        if metadata and filename in metadata:
            if metadata[filename].get("milestone"):
                continue

        file_path = os.path.join(backup_dir, filename)
        if os.path.isfile(file_path):
            if os.path.getmtime(file_path) < cutoff:
                try:
                    os.remove(file_path)
                    if metadata and filename in metadata:
                        del metadata[filename]
                    print(f"{INFO} Pruned old backup: {filename}")
                except Exception as e:
                    print(f"{ERROR} Error pruning {filename}: {e}")

def list_backups(backup_dir):
    metadata_path = os.path.join(backup_dir, METADATA_FILE)
    if not os.path.exists(metadata_path):
        print(f"{WARNING} No metadata found.")
        return

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    print(f"{HEADER}{'Timestamp':<25} {'Type':<10} {'Milestone':<10} {'Label'}{RESET}")
    print("-" * 70)
    for filename, info in sorted(metadata.items(), key=lambda x: x[1]['timestamp'], reverse=True):
        milestone = "*" if info.get("milestone") else " "
        print(f"{info['timestamp']:<25} {info['type']:<10} {milestone:<10} {info.get('label', '')}")

def restore_backup(backup_dir, target_dir, timestamp=None):
    metadata_path = os.path.join(backup_dir, METADATA_FILE)
    if not os.path.exists(metadata_path):
        print(f"{ERROR} No metadata found.")
        return

    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    if timestamp:
        backups = [b for b in metadata.values() if b['timestamp'] == timestamp]
    else:
        # Latest backup
        backups = [sorted(metadata.values(), key=lambda x: x['timestamp'], reverse=True)[0]]

    if not backups:
        print(f"{ERROR} Backup not found.")
        return

    info = backups[0]
    backup_filename = info['backup_filename']
    original_filename = info['original_filename']
    dest_path = os.path.join(target_dir, original_filename)

    if info['type'] == 'full':
        shutil.copy(os.path.join(backup_dir, backup_filename), dest_path)
    else:
        # Delta restoration
        parent_filename = info['parent']
        parent_path = os.path.join(backup_dir, parent_filename)
        delta_path = os.path.join(backup_dir, backup_filename)
        try:
            cmd = ["xdelta3", "-d", "-s", parent_path, delta_path, dest_path]
            subprocess.run(cmd, check=True)
        except Exception as e:
            print(f"{ERROR} Error restoring delta: {e}")
            return

    print(f"{SUCCESS} Restored {original_filename} from {info['timestamp']} ({info['type']})")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Monitor a folder for save-state files and back them up.")
    parser.add_argument("source", nargs="?", help="Directory to monitor")
    parser.add_argument("backup", nargs="?", help="Directory to store backups")
    parser.add_argument("--list", action="store_true", help="List all backups")
    parser.add_argument("--restore", help="Restore backup with given timestamp (omitting timestamp restores latest)")
    parser.add_argument("--restore-to", help="Directory to restore to (defaults to source)")
    parser.add_argument("--retention", type=int, default=7, help="Days to retain backups (default: 7)")
    parser.add_argument("--extensions", nargs="+", help="File extensions to monitor (e.g., .sav .dsv)")
    parser.add_argument("--recursive", action="store_true", help="Monitor subdirectories recursively")
    parser.add_argument("--cpu-threshold", type=int, default=60, help="CPU usage threshold to delay backups (default: 60)")
    parser.add_argument("--use-delta", action="store_true", help="Use delta compression for backups")
    parser.add_argument("--git-sync", action="store_true", help="Automatically push milestones to GitHub")

    args = parser.parse_args()

    # Handle positional arguments vs optional flags for backward compatibility
    source_dir = args.source
    backup_dir = args.backup

    if not backup_dir:
        print(f"{ERROR} Backup directory is required.")
        sys.exit(1)

    backup_dir = os.path.abspath(backup_dir)

    if args.list:
        list_backups(backup_dir)
        return

    if args.restore or (hasattr(args, 'restore') and args.restore is None and '--restore' in sys.argv):
        target = args.restore_to or source_dir
        if not target:
            print(f"{ERROR} Must specify restoration target (--restore-to or source positional arg).")
            sys.exit(1)
        restore_backup(backup_dir, os.path.abspath(target), timestamp=args.restore)
        return

    if not source_dir:
        print(f"{ERROR} Source directory is required for monitoring.")
        sys.exit(1)

    source_dir = os.path.abspath(source_dir)

    # Load AI if needed (can be slow, so we do it before starting)
    load_ai()

    if not os.path.exists(source_dir):
        print(f"{ERROR} '{source_dir}' does not exist.")
        sys.exit(1)

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    event_handler = SaveBackupHandler(
        backup_dir,
        extensions=args.extensions,
        retention_days=args.retention,
        cpu_threshold=args.cpu_threshold,
        use_delta=args.use_delta,
        git_sync=args.git_sync
    )
    observer = Observer()
    observer.schedule(event_handler, source_dir, recursive=args.recursive)
    
    print(f"{HEADER} Monitoring: {source_dir}{RESET}")
    print(f"{INFO} Backups to: {backup_dir}")
    print(f"{INFO} Retention: {args.retention} days")
    if args.extensions:
        print(f"{INFO} Extensions: {', '.join(args.extensions)}")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
