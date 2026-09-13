#!/usr/bin/env python3
"""Smoke-test OpenCode Go vision model on one dataset image."""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def png_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def chat_completion(*, model: str, messages: list[dict], session_id: str) -> dict:
    api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
    if not api_key:
        raise SystemExit("OPENCODE_GO_API_KEY is not set")

    base_url = os.environ.get("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 800,
        "temperature": 0,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "buy-or-wait/1.0",
            "x-opencode-session": session_id,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {detail[:1000]}") from exc


def main() -> int:
    load_env()
    model = os.environ.get("OPENCODE_GO_VISION_MODEL", "deepseek-v4-flash-vision-exp")
    image_path = REPO_ROOT / "dataset/media/images/image_05.png"
    if not image_path.exists():
        raise SystemExit(f"Missing image: {image_path}")

    system = (
        "You extract financial amounts from receipt images. "
        "Return ONLY valid JSON with keys: document_type, amount, currency, "
        "amount_role, due_date, amount_in_words, notes."
    )
    user_text = (
        "Linked financial event:\n"
        "- description: Outstanding telecom bill\n"
        "- direction: debit\n"
        "- status: pending\n"
        "- currency: INR\n"
        "Pick the amount due by the due date on the bill, not the late amount."
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": png_data_url(image_path)}},
            ],
        },
    ]

    print(f"Testing model={model}")
    print(f"Image={image_path.name}")
    payload = chat_completion(model=model, messages=messages, session_id="buy-or-wait-vision-test")
    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {})
    print("\n--- model response ---")
    print(content)
    print("\n--- usage ---")
    print(json.dumps(usage, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
