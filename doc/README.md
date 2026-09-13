# Workspace Knowledge Base

Shared memory for AI agents working in this repo. Survives across chat sessions.

## Quick use

| You type | What happens |
|----------|--------------|
| `/setup` | Scaffold `doc/` + Cursor rule (first time in a repo) |
| `/recall` | Agent loads `KNOWLEDGE.md` (+ chunks) so you skip re-explaining context |
| `/ingest` | Agent summarizes the chat, diffs against the KB, lists addable chunks; you choose what to save |

Agents also update `KNOWLEDGE.md` automatically when they hit important findings (see `.cursor/rules/workspace-knowledge.mdc`).

## Layout

```text
doc/
├── KNOWLEDGE.md      # Master file — start here
├── README.md         # This file
├── chunks/           # Optional deep-dive topic files
│   └── <topic>.md
└── research/         # Internal research — NOT for submission
    └── orchestrate-winners-and-scoring.md
```

**Note:** Files under `doc/research/` are for your prep only. Exclude from `code.zip` and do not merge into `log.txt` for HackerRank upload.

## What belongs here

- Decisions, architecture, and approach
- Non-obvious bugs and fixes
- Current progress and next steps
- Commands, paths, and conventions

## What to avoid

- Secrets and API keys
- Full chat dumps (use `/ingest` summaries instead)
- Duplicating `AGENTS.md` / `README.md` verbatim

## Copy to new workspaces

Run `/setup` in any repo. Personal skills live in `~/.cursor/skills/setup/`, `recall/`, and `ingest/`.
