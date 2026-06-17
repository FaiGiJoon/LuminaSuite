import struct
from color_constants import SUCCESS, WARNING
from ..core.base_module import BaseModule

class HandheldModule(BaseModule):
    """
    Module for 3DS and Wii U, focusing on MSBT (Message Binary Text) files.
    """

    def extract_strings(self):
        """
        Simplified MSBT parser logic.
        MSBT usually has sections like LBL1, ATR1, TXT2.
        Strings are in the TXT2 section.
        """
        with open(self.file_path, 'rb') as f:
            data = f.read()

        if data[:8] != b'MsgStdBn':
            raise ValueError("Not a valid MSBT file.")

        # This is a placeholder for a full MSBT parser.
        # In a real implementation, we would parse the section headers.
        # For this framework, we'll implement a robust regex-based extraction
        # for sequences of UTF-16 strings often found in MSBT.
        import re
        # MSBT strings are null-terminated UTF-16LE.
        # We search for sequences of bytes that look like printable UTF-16LE.
        # Since \u is not valid in byte regex, we check for common Japanese byte ranges in UTF-16LE.
        # Hiragana/Katakana are roughly 00 30 to FF 30. Kanji starts around 00 4E.
        pattern = re.compile(rb'(?:[\x20-\x7E\x00-\xFF][\x00\x30-\x9F])+\x00\x00')
        matches = pattern.finditer(data)

        self.manifest = {}
        for i, match in enumerate(matches):
            try:
                text = match.group().decode('utf-16le').strip('\x00')
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
        Inject strings back. MSBT is tricky because of offsets.
        For simplicity, this implementation replaces strings in-place if they fit.
        """
        with open(self.file_path, 'rb') as f:
            data = bytearray(f.read())

        # Sort offsets in reverse to avoid shifting issues if we were to resize
        # (though here we'll stick to in-place or padding)
        for string_id, translated_text in translations.items():
            if string_id not in self.manifest:
                continue

            info = self.manifest[string_id]
            offset = info['offset']
            max_len = info['length']

            # Encode as UTF-16LE and add null terminator
            new_data = (translated_text + '\x00').encode('utf-16le')

            if len(new_data) <= max_len:
                # Pad with nulls if shorter
                new_data = new_data.ljust(max_len, b'\x00')
                data[offset:offset+max_len] = new_data
            else:
                print(f"{WARNING} Translation for {string_id} too long, skipping.")

        with open(self.output_path, 'wb') as f:
            f.write(data)
        print(f"{SUCCESS} Injected strings into {self.output_path}")
