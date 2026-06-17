import os
import json
import time
import platform
import threading
import tkinter as tk
from tkinter import ttk
import requests
from PIL import Image
import mss
import pytesseract
from color_constants import INFO, WARNING, ERROR

# Default configuration
DEFAULT_CONFIG = {
    "emulator_name": "Cemu",
    "ocr_region_offset": {"top": 400, "left": 100, "width": 600, "height": 150},
    "ollama_url": "http://localhost:11434/api/generate",
    "ollama_model": "llama3",
    "update_interval_ms": 1000,
    "overlay_opacity": 0.8,
    "font_size": 16
}

class TranslatorApp:
    def __init__(self, config_path="config.json", setup_ui=True):
        self.config = self.load_config(config_path)
        self.running = True
        self.last_text = ""
        self.translation_in_progress = False
        self.window_bounds = None # Current tracked emulator bounds

        # macOS specific
        self.is_macos = platform.system() == "Darwin"
        self.Quartz = False
        if self.is_macos:
            try:
                from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
                self.Quartz = True
            except ImportError:
                print(f"{WARNING} Quartz not found. Window tracking disabled.")

        if setup_ui:
            self.setup_ui()

    def load_config(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        return DEFAULT_CONFIG

    def setup_ui(self):
        self.root = tk.Tk()
        self.root.title("Game Translator Overlay")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", self.config["overlay_opacity"])
        self.root.overrideredirect(True) # Remove window decorations

        self.label = tk.Label(
            self.root,
            text="Waiting for text...",
            font=("Arial", self.config["font_size"]),
            bg="black",
            fg="white",
            wraplength=600,
            justify="left"
        )
        self.label.pack(expand=True, fill="both", padx=10, pady=10)

        # Make window draggable for manual positioning
        self.label.bind("<Button-1>", self.start_move)
        self.label.bind("<B1-Motion>", self.do_move)

        # Add a way to quit
        self.root.bind("<Escape>", lambda e: self.quit())

    def quit(self):
        self.running = False
        self.root.destroy()

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")

    def capture_screen(self):
        with mss.mss() as sct:
            offset = self.config["ocr_region_offset"]

            # Use tracked window position if available, otherwise absolute from offset
            base_x = 0
            base_y = 0
            if self.window_bounds:
                base_x = self.window_bounds['X']
                base_y = self.window_bounds['Y']

            monitor = {
                "top": int(base_y + offset["top"]),
                "left": int(base_x + offset["left"]),
                "width": int(offset["width"]),
                "height": int(offset["height"])
            }

            try:
                sct_img = sct.grab(monitor)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception as e:
                print(f"{ERROR} Capture error: {e}")
                return None

    def perform_ocr(self, image):
        # Tesseract OCR for Japanese (jpn)
        try:
            text = pytesseract.image_to_string(image, lang='jpn')
            # Clean up whitespace
            return text.strip()
        except Exception as e:
            print(f"{ERROR} OCR Error: {e}")
            return ""

    def translate_text(self, text):
        if not text:
            return ""

        prompt = f"Translate the following Japanese game text into natural English. Only provide the translation, nothing else.\n\nText: {text}"

        try:
            response = requests.post(
                self.config["ollama_url"],
                json={
                    "model": self.config["ollama_model"],
                    "prompt": prompt,
                    "stream": False
                },
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except Exception as e:
            print(f"{ERROR} Translation Error: {e}")
            return f"[Error: {e}]"

    def update_loop(self):
        if not self.running:
            return

        try:
            # 1. Update tracked window position
            self.track_window()

            # 2. If not already translating, start OCR/Translation in a thread
            if not self.translation_in_progress:
                threading.Thread(target=self.process_translation_threaded, daemon=True).start()

        except Exception as e:
            print(f"{ERROR} Loop Error: {e}")

        # Schedule next update
        self.root.after(self.config["update_interval_ms"], self.update_loop)

    def process_translation_threaded(self):
        self.translation_in_progress = True
        try:
            image = self.capture_screen()
            if image:
                current_text = self.perform_ocr(image)
                if current_text and current_text != self.last_text:
                    translation = self.translate_text(current_text)
                    if translation:
                        # Update UI in main thread
                        self.root.after(0, lambda: self.label.config(text=translation))
                        self.last_text = current_text
        except Exception as e:
            print(f"{ERROR} Threaded processing error: {e}")
        finally:
            self.translation_in_progress = False

    def track_window(self):
        if not self.is_macos or not self.Quartz:
            return

        from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        target_name = self.config["emulator_name"]

        for window in window_list:
            name = window.get('kCGWindowName', '')
            owner_name = window.get('kCGWindowOwnerName', '')

            if target_name.lower() in name.lower() or target_name.lower() in owner_name.lower():
                bounds = window.get('kCGWindowBounds')
                if bounds:
                    self.window_bounds = bounds

                    # Update position only if it's the first time or window moved
                    # This allows some manual offset but will re-snap if the emulator moves
                    # For simplicity in this version, we'll follow it closely
                    x = int(bounds['X'])
                    y = int(bounds['Y'])
                    w = int(bounds['Width'])
                    h = int(bounds['Height'])

                    overlay_x = x + (w // 2) - 300
                    overlay_y = y + h - 100
                    self.root.geometry(f"+{overlay_x}+{overlay_y}")
                    return

        self.window_bounds = None

    def run(self):
        # Start update loop
        self.root.after(100, self.update_loop)
        self.root.mainloop()

if __name__ == "__main__":
    app = TranslatorApp()
    app.run()
