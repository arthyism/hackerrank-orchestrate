#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for "Buy or Wait?".
# Safe to run repeatedly and against cached/partially prepared state.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Debian/Ubuntu ships venv/ensurepip separately; install only when missing so
# repeat runs (and snapshot-backed boots that already have it) stay fast.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq python3-venv
fi

# Project virtualenv holds the pinned requirements (README convention).
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

python -m pip install --quiet --upgrade pip
pip install --quiet -r code/requirements.txt

# The deterministic engine fills blank event amounts from a cached vision file.
# It ships inside code.zip, but the git checkout omits code/cache/ (gitignored),
# so restore it here to keep `python3 code/main.py --no-llm` fully reproducible
# with no API key. The LLM path (with OPENCODE_GO_API_KEY) regenerates it anyway.
if [ ! -f code/cache/image_facts.json ] && [ -f code.zip ]; then
  python3 -c "import zipfile; zipfile.ZipFile('code.zip').extract('code/cache/image_facts.json', '.')"
fi

echo "install.sh complete: venv ready, image cache present=$( [ -f code/cache/image_facts.json ] && echo yes || echo no )"
