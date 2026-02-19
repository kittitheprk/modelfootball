import os
from pathlib import Path

def _load_gemini_api_key():
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        print(f"Found key in env var: {env_key[:5]}...{env_key[-5:]}")
        return env_key, "env:GEMINI_API_KEY"

    key_file = Path("gemini_key.txt")
    if not key_file.exists():
        print("gemini_key.txt not found")
        return None, None

    try:
        raw = key_file.read_text(encoding="utf-8")
    except Exception:
        print("Error reading gemini_key.txt")
        return None, None

    for line in raw.splitlines():
        cleaned = line.strip().strip('"').strip("'")
        if not cleaned or cleaned.startswith("#"):
            continue
        if "=" in cleaned:
            cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
        if cleaned:
            print(f"Found key in file: {cleaned[:5]}...{cleaned[-5:]}")
            return cleaned, "file:gemini_key.txt"
    print("No key found in file")
    return None, None

_load_gemini_api_key()
