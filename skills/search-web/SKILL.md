---
name: search-web
description: Web search + research summaries using the OpenRouter Web plugin (via a local script). Use when the user asks to “sprawdź w sieci…”, “wyszukaj informacje…”, “znajdź źródła/linki…”, “zrób research online…”, or when you need a short summary with citations/URLs. Configure the query and the number of sources/results.
---

# Search Web

## Overview

Run a deterministic web-search call through OpenRouter and return a Polish summary with citations plus a short list of sources (URLs).

## Quick Start

- Ensure `OPENROUTER_API_KEY` is present in the environment (do not print it).
- Run:
  - `python /home/dev/.codex/skills/search-web/scripts/search_web.py --query "Józef Piłsudski biografia najważniejsze fakty" --max-results 5`

## Workflow

1. Choose the query (what to search for).
2. Choose the number of results/sources (`--max-results`, typically 3–8; default 5).
3. Run the script and paste the returned summary + sources back to the user.

Notes:
- For queries about **Codex CLI changelog/release notes** with a version range (e.g. `0.80-0.87`), the script will automatically generate a **TL;DR from official GitHub Releases** (`openai/codex`) instead of using the OpenRouter Web plugin.
- For other queries, the script uses an **auto strategy**:
  - If the question looks **banal/obvious**, it runs a single web search + summary.
  - If the question looks **średnie/trudne**, it will first ask whether to do:
    - **simple**: one search pass (`--mode simple`), or
    - **deep**: 3 iterative searches + final synthesis (`--mode deep`).

## Output Rules

- Prefer Polish output unless the user asks otherwise.
- Include citations in-text (e.g., `[1]`) and a short `Źródła:` section with URLs.
- If the answer is disputed or unclear, present 2–3 viewpoints and cite each claim.

## Script

Use `scripts/search_web.py`.

Arguments:
- `--query` (required): search request text
- `--max-results` (optional): how many web results the plugin can use (default `5`)
- `--model` (optional): OpenRouter model (default `google/gemini-2.5-flash-lite`)
- `--lang` (optional): language code used in the prompt (default `pl`)
- `--mode` (optional): `auto` (default), `simple` (1 pass), `deep` (3 passes + synthesis)

Notes:
- Do not log or echo `OPENROUTER_API_KEY`.
- If `OPENROUTER_API_KEY` is missing, instruct the user to set it in their shell profile and restart the terminal.

### scripts/
`search_web.py` calls OpenRouter `chat/completions` with the `web` plugin and prints the assistant’s final message.

### references/
None.
