import json
import requests
import os
from color_constants import ERROR

class TranslationEngine:
    def __init__(self, ollama_url="http://localhost:11434/api/generate", model="llama3"):
        self.ollama_url = ollama_url
        self.model = model

    def translate(self, text, context=""):
        if not text or not text.strip():
            return text

        prompt = (
            f"Translate the following Japanese game text into natural English. "
            f"Context: {context}. "
            f"Important: Keep the translation as concise as possible to avoid byte length issues. "
            f"Only provide the translation, nothing else.\n\n"
            f"Text: {text}"
        )

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except Exception as e:
            print(f"{ERROR} Translation Error: {e}")
            return None

class ManifestManager:
    @staticmethod
    def load(path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    @staticmethod
    def save(manifest, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)

def check_byte_safety(original, translated, max_bytes=None):
    """
    Checks if the translated text fits within byte constraints.
    """
    orig_bytes = len(original.encode('utf-8'))
    trans_bytes = len(translated.encode('utf-8'))

    limit = max_bytes if max_bytes is not None else orig_bytes

    if trans_bytes > limit:
        return False, trans_bytes, limit
    return True, trans_bytes, limit
