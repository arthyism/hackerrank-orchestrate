# Buy or Wait? agent

Deterministic cash engine. LLM evidence parsing is not required for the first sample eval.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r code/requirements.txt
```

API keys (later, for images/messages) live in repo-root `.env`:

- `OPENCODE_GO_API_KEY`
- `OPENCODE_GO_BASE_URL` (default `https://opencode.ai/zen/go/v1`)

## Run

```bash
# 15-row DEV split (default — iterate here)
python3 code/main.py --eval-samples

# 10-row HOLDOUT — only after we stop tuning
python3 code/main.py --eval-samples --eval-split holdout

# one request
python3 code/main.py --request request_01

# full 250-row submission file
python3 code/main.py
```

Writes repo-root `output.csv`.
