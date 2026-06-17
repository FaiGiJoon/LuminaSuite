#!/usr/bin/env python3
"""
macOS Nintendo ROM Tagger
-------------------------
Parses headers of .gba and .iso/.gcm files and injects native macOS
Extended Attributes (Spotlight metadata) and Finder Color Tags.

Verification:
To verify the tags after running the script, use the 'mdls' command:
    mdls /path/to/rom/file.gba
"""

import os
import subprocess
import xattr
import plistlib
import argparse
from color_constants import SUCCESS, INFO, WARNING, ERROR, HEADER, RESET

def parse_gba_header(file_path):
    """
    Parses .gba header.
    Title: offset 0xA0, 12 bytes
    Code: offset 0xAC, 4 bytes
    """
    with open(file_path, 'rb') as f:
        f.seek(0xA0)
        title_bytes = f.read(12)
        code_bytes = f.read(4)

    title = title_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()
    code = code_bytes.decode('ascii', errors='ignore').strip()

    # Prepend AGB- as seen in standard identifiers for GBA
    if code and not code.startswith('AGB-'):
        code = f"AGB-{code}"

    return title, code

def parse_iso_header(file_path):
    """
    Parses .iso / .gcm (GameCube) header.
    Code: offset 0x00, 6 bytes
    Title: offset 0x20, 64 bytes
    """
    with open(file_path, 'rb') as f:
        code_bytes = f.read(6)
        f.seek(0x20)
        title_bytes = f.read(64)

    code = code_bytes.decode('ascii', errors='ignore').strip()
    title = title_bytes.split(b'\x00')[0].decode('ascii', errors='ignore').strip()

    return title, code

def set_metadata(file_path, title, code):
    """
    Sets macOS Extended Attributes using xattr.
    All attributes are stored as binary plists for native compatibility.
    """
    attrs = xattr.xattr(file_path)

    # Helper to dump binary plist
    def to_plist(val):
        return plistlib.dumps(val, fmt=plistlib.FMT_BINARY)

    # com.apple.metadata:kMDItemTitle
    attrs.set('com.apple.metadata:kMDItemTitle', to_plist(title))

    # com.apple.metadata:kMDItemIdentifier
    attrs.set('com.apple.metadata:kMDItemIdentifier', to_plist(code))

    # com.apple.metadata:kMDItemWhereFroms (Array)
    attrs.set('com.apple.metadata:kMDItemWhereFroms', to_plist(["Nintendo ROM Library"]))

def set_finder_tag(file_path, color):
    """
    Applies Finder Color Tags using osascript.
    """
    # Mapping for label index: 0=None, 1=Orange, 2=Red, 3=Yellow, 4=Blue, 5=Purple, 6=Green, 7=Gray
    color_map = {
        "Green": 6,
        "Purple": 5
    }
    index = color_map.get(color, 0)

    # Properly escape the path for AppleScript
    abs_path = os.path.abspath(file_path).replace('"', '\\"')
    apple_script = f'tell application "Finder" to set label index of (POSIX file "{abs_path}") to {index}'

    subprocess.run(['osascript', '-e', apple_script], capture_output=True)

def force_spotlight_index(file_path):
    """
    Forces Spotlight to index the file using mdimport.
    """
    subprocess.run(['mdimport', file_path], capture_output=True)

def process_directory(directory):
    """
    Processes all .gba, .iso, and .gcm files in the directory.
    """
    if not os.path.isdir(directory):
        print(f"{ERROR} {directory} is not a valid directory.")
        return

    files = [f for f in os.listdir(directory) if f.lower().endswith(('.gba', '.iso', '.gcm'))]
    if not files:
        print(f"{WARNING} No compatible ROM files found in {directory}")
        return

    print(f"{HEADER} Processing {len(files)} files in {directory}...{RESET}")

    for i, filename in enumerate(files):
        file_path = os.path.join(directory, filename)
        ext = os.path.splitext(filename)[1].lower()

        try:
            if ext == '.gba':
                title, code = parse_gba_header(file_path)
                color = "Green"
            else: # .iso or .gcm
                title, code = parse_iso_header(file_path)
                color = "Purple"

            if not title or not code:
                print(f"{WARNING} [{i+1}/{len(files)}] Skipping {filename}: Could not parse header data.")
                continue

            print(f"{INFO} [{i+1}/{len(files)}] Tagging: {filename}")
            print(f"    - Title: {title}")
            print(f"    - Code:  {code}")

            set_metadata(file_path, title, code)
            set_finder_tag(file_path, color)
            force_spotlight_index(file_path)

        except PermissionError:
            print(f"{ERROR} [{i+1}/{len(files)}] Permission Denied: Could not access {filename}.")
        except Exception as e:
            print(f"{ERROR} [{i+1}/{len(files)}] Error processing {filename}: {e}")

    print(f"\n{SUCCESS} Finished tagging {len(files)} files.")

def main():
    parser = argparse.ArgumentParser(description="macOS Nintendo ROM Tagger - Parses headers and injects Extended Attributes.")
    parser.add_argument("--dir", required=True, help="Directory containing .gba, .iso, or .gcm files.")

    args = parser.parse_args()
    process_directory(args.dir)

if __name__ == "__main__":
    main()
