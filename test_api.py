"""Quick test: verify OpenRouter API key and model are functional."""
import os
from pathlib import Path

API_FILE = Path(__file__).resolve().parent / "API.txt"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def read_api_file():
    if not API_FILE.exists():
        return {}
    out = {}
    for line in API_FILE.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        out[k.strip().lower()] = v.strip()
    return out


def main():
    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed — run: pip install requests")
        return

    creds = read_api_file()
    api_key = os.environ.get("OPENROUTER_API_KEY") or creds.get("key")
    model = os.environ.get("OPENROUTER_MODEL") or creds.get("model") or "google/gemma-4-26b-a4b-it:free"

    print(f"API key : {'(from env)' if os.environ.get('OPENROUTER_API_KEY') else '(from API.txt)'}")
    print(f"Key preview : {api_key[:8]}...{api_key[-4:] if api_key and len(api_key) > 12 else ''}")
    print(f"Model   : {model}")
    print()

    if not api_key:
        print("ERROR: no API key found in API.txt or OPENROUTER_API_KEY env var")
        return

    # Minimal single-turn request
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say exactly: OK"}],
        "max_tokens": 10,
    }

    print("Sending test request to OpenRouter...")
    resp = requests.post(
        url=f"{OPENROUTER_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=30,
    )

    print(f"HTTP status : {resp.status_code}")
    print(f"Raw body    : {resp.text[:500]}")

    if resp.status_code == 200:
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print(f"\nModel replied: {content!r}")
        print("\nSUCCESS — key and model are working.")
    elif resp.status_code == 401:
        print("\nFAILED — API key is invalid or expired.")
    elif resp.status_code == 429:
        print("\nFAILED — still rate limited. Try again later or switch to a different model.")
    elif resp.status_code == 404:
        print("\nFAILED — model not found. The model name may be wrong or not available on your plan.")
    else:
        print(f"\nFAILED — unexpected status {resp.status_code}.")


if __name__ == "__main__":
    main()
