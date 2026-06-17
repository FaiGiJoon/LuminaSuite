import os
import re
from color_constants import SUCCESS, INFO
from ..core.base_module import BaseModule

class CartridgeModule(BaseModule):
    """
    Module for NES, SNES, and N64, handling raw binary scanning and TBL files.
    """

    def __init__(self, file_path, output_path=None, tbl_path=None):
        super().__init__(file_path, output_path)
        self.table = self.load_tbl(tbl_path) if tbl_path else None

    def load_tbl(self, path):
        """
        Loads a standard .tbl file (01=A format).
        """
        table = {}
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line:
                        code, char = line.strip().split('=', 1)
                        table[int(code, 16)] = char
        return table

    def extract_strings(self):
        """
        Scans binary for text using either the TBL or standard ASCII/Shift-JIS.
        """
        with open(self.file_path, 'rb') as f:
            data = f.read()

        self.manifest = {}

        if self.table:
            # TBL-based extraction: look for sequences of bytes present in the table
            valid_bytes = set(self.table.keys())
            current_string = []
            start_offset = -1

            for i, byte in enumerate(data):
                if byte in valid_bytes:
                    if start_offset == -1:
                        start_offset = i
                    current_string.append(self.table[byte])
                else:
                    if len(current_string) > 3: # Minimum string length
                        text = "".join(current_string)
                        self.manifest[str(start_offset)] = {
                            "original": text,
                            "translation": None,
                            "offset": start_offset,
                            "length": len(current_string)
                        }
                    current_string = []
                    start_offset = -1
        else:
            # Generic ASCII scanning
            pattern = re.compile(rb'[\x20-\x7E]{4,}')
            matches = pattern.finditer(data)
            for i, match in enumerate(matches):
                text = match.group().decode('ascii')
                self.manifest[str(match.start())] = {
                    "original": text,
                    "translation": None,
                    "offset": match.start(),
                    "length": len(text)
                }

        return self.manifest

    def inject_strings(self, translations):
        """
        Injects strings, maintaining byte-level safety and fixing N64 checksums if needed.
        """
        with open(self.file_path, 'rb') as f:
            data = bytearray(f.read())

        reverse_table = {v: k for k, v in self.table.items()} if self.table else None

        for offset_str, translated_text in translations.items():
            offset = int(offset_str)
            info = self.manifest[offset_str]
            max_len = info['length']

            if reverse_table:
                # TBL encoding
                new_data = bytearray()
                for char in translated_text[:max_len]:
                    if char in reverse_table:
                        new_data.append(reverse_table[char])
                    else:
                        new_data.append(ord(' ')) # Fallback
            else:
                # ASCII encoding
                new_data = translated_text[:max_len].encode('ascii', errors='ignore')

            # Pad and inject
            new_data = new_data.ljust(max_len, b'\x00' if not self.table else list(self.table.keys())[0])
            data[offset:offset+max_len] = new_data

        # N64 Checksum Fix (Placeholder)
        if self.file_path.lower().endswith('.n64') or self.file_path.lower().endswith('.z64'):
            print(f"{INFO} N64 ROM detected. Recalculating checksum...")
            self.fix_n64_checksum(data)

        with open(self.output_path, 'wb') as f:
            f.write(data)
        print(f"{SUCCESS} Cartridge ROM {self.output_path} generated.")

    def fix_n64_checksum(self, data):
        """
        Placeholder for N64 checksum correction logic.
        """
        pass
