import argparse
import os
import sys
from color_constants import SUCCESS, INFO, WARNING, ERROR, HEADER, RESET
from omni.core.engine import TranslationEngine, ManifestManager
from omni.modules.handheld import HandheldModule
from omni.modules.disc import DiscModule
from omni.modules.cartridge import CartridgeModule

def main():
    parser = argparse.ArgumentParser(description="Omni-Translate: Automated ROM Translation Framework")
    parser.add_argument("--platform", required=True, choices=["handheld", "disc", "cartridge"],
                        help="Platform type (handheld=3DS/WiiU, disc=GC/Wii, cartridge=NES/SNES/N64)")
    parser.add_argument("--file", required=True, help="Path to the ROM/file to translate")
    parser.add_argument("--output", help="Path for the translated output file")
    parser.add_argument("--manifest", help="Path to the JSON manifest (will be created if not exists)")
    parser.add_argument("--translate", action="store_true", help="Perform translation via LLM")
    parser.add_argument("--inject", action="store_true", help="Inject translations from manifest into file")
    parser.add_argument("--model", default="llama3", help="Ollama model to use")
    parser.add_argument("--tbl", help="Path to .tbl file (for cartridge platform)")

    args = parser.parse_args()

    # 1. Initialize Module
    if args.platform == "handheld":
        module = HandheldModule(args.file, args.output)
    elif args.platform == "disc":
        module = DiscModule(args.file, args.output)
    elif args.platform == "cartridge":
        module = CartridgeModule(args.file, args.output, args.tbl)
    else:
        print(f"{ERROR} Unsupported platform.")
        sys.exit(1)

    manifest_path = args.manifest or f"{args.file}.manifest.json"

    # 2. Extract or Load Manifest
    if os.path.exists(manifest_path):
        print(f"{INFO} Loading existing manifest: {manifest_path}")
        manifest = ManifestManager.load(manifest_path)
    else:
        print(f"{INFO} Extracting strings from {args.file}...")
        manifest = module.extract_strings()
        ManifestManager.save(manifest, manifest_path)

    # 3. Translate
    if args.translate:
        engine = TranslationEngine(model=args.model)
        print(f"{HEADER} Translating strings via Ollama ({args.model})...{RESET}")
        for string_id, info in manifest.items():
            if not info.get("translation"):
                translation = engine.translate(info["original"])
                if translation:
                    info["translation"] = translation
                    print(f"{SUCCESS} Translated: {info['original']} -> {translation}")
        ManifestManager.save(manifest, manifest_path)

    # 4. Inject
    if args.inject:
        print(f"{INFO} Injecting translations into {args.output or 'default output'}...")
        translations = {k: v["translation"] for k, v in manifest.items() if v.get("translation")}
        module.inject_strings(translations)

if __name__ == "__main__":
    main()
