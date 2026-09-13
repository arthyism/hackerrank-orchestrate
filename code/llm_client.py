"""OpenCode Go chat client (OpenAI-compatible /chat/completions)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
USAGE_PATH = ROOT / "code" / "cache" / "usage.jsonl"


def load_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def has_api_key() -> bool:
    load_env()
    return bool(os.environ.get("OPENCODE_GO_API_KEY"))


def chat_completion(
    *,
    messages: list[dict[str, Any]],
    model: Optional[str] = None,
    session_id: str = "buy-or-wait",
    max_tokens: int = 700,
    temperature: float = 0,
) -> dict[str, Any]:
    load_env()
    api_key = os.environ.get("OPENCODE_GO_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENCODE_GO_API_KEY is not set")
    model = model or os.environ.get("OPENCODE_GO_TEXT_MODEL", "glm-5.3-flash")
    base_url = os.environ.get("OPENCODE_GO_BASE_URL", "https://opencode.ai/zen/go/v1").rstrip("/")
    url = f"{base_url}/chat/completions"
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    _log_usage(model=model, session_id=session_id, payload=payload)
    return payload


def extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("No JSON object in model output")
    return json.loads(text[start : end + 1])


def _log_usage(*, model: str, session_id: str, payload: dict[str, Any]) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "model": model,
        "session_id": session_id,
        "usage": payload.get("usage") or {},
    }
    with USAGE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
