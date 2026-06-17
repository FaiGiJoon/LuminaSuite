import os
import re
from color_constants import SUCCESS, WARNING
from ..core.base_module import BaseModule

class DiscModule(BaseModule):
    """
    Module for GameCube and Wii, handling ISO/WBFS and common text files.
    """

    def extract_strings(self):
        """
        Extracts strings from common disc-based text formats (.msg, .str).
        """
        # For this module, we'll implement a scanner for Shift-JIS strings
        # which are ubiquitous in GC/Wii titles.
        # Use memory mapping or read in chunks if file is large (> 100MB)
        file_size = os.path.getsize(self.file_path)
        if file_size > 100 * 1024 * 1024:
            import mmap
            with open(self.file_path, 'rb') as f:
                data = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        else:
            with open(self.file_path, 'rb') as f:
                data = f.read()

        # Shift-JIS regex for Japanese characters
        # Matches sequences of bytes in the SJIS range
        pattern = re.compile(rb'[\x81-\x9F\xE0-\xEF][\x40-\x7E\x80-\xFC]+')
        matches = pattern.finditer(data)

        self.manifest = {}
        for i, match in enumerate(matches):
            try:
                text = match.group().decode('shift-jis')
                if len(text) > 1:
                    self.manifest[str(i)] = {
                        "original": text,
                        "translation": None,
                        "offset": match.start(),
                        "length": match.end() - match.start()
                    }
            except UnicodeDecodeError:
                continue

        return self.manifest

    def inject_strings(self, translations):
        """
        Injects strings back, ensuring byte-safety for Shift-JIS.
        """
        with open(self.file_path, 'rb') as f:
            data = bytearray(f.read())

        for string_id, translated_text in translations.items():
            if string_id not in self.manifest:
                continue

            info = self.manifest[string_id]
            offset = info['offset']
            max_len = info['length']

            # Encode as Shift-JIS (or UTF-8/ASCII if the game supports it,
            # but usually SJIS for these consoles)
            try:
                new_data = translated_text.encode('shift-jis')
            except UnicodeEncodeError:
                # Fallback to ASCII for English if SJIS fails for some chars
                new_data = translated_text.encode('ascii', errors='ignore')

            if len(new_data) <= max_len:
                # Pad with spaces or nulls
                new_data = new_data.ljust(max_len, b'\x00')
                data[offset:offset+max_len] = new_data
            else:
                print(f"{WARNING} Translation for {string_id} too long, skipping.")

        with open(self.output_path, 'wb') as f:
            f.write(data)
        print(f"{SUCCESS} Disc-based file {self.output_path} updated.")
