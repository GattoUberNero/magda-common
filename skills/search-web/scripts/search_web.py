#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GITHUB_RELEASES_API = "https://api.github.com/repos/openai/codex/releases?per_page=100"


def _die(message: str, code: int = 2) -> "None":
    print(message, file=sys.stderr)
    raise SystemExit(code)


def _request(api_key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        _die(f"OpenRouter HTTP error: {e.code}\n{raw}")
    except Exception as e:
        _die(f"OpenRouter request failed: {e}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        _die(f"OpenRouter returned non-JSON response:\n{raw}")


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Union[Dict[str, Any], List[Any]]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        _die(f"HTTP error: {e.code}\n{raw}")
    except Exception as e:
        _die(f"HTTP request failed: {e}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        _die(f"Non-JSON response:\n{raw}")


def _extract_codex_cli_range(query: str) -> Optional[Tuple[int, int]]:
    """
    Returns (min_minor, max_minor) for query ranges like:
    - 0.80-0.87 / 0.80-87 / 0.80 do 0.87
    - also supports a single version like 0.87
    """
    minors = [int(m.group(1)) for m in re.finditer(r"0\.(\d{2})(?:\.\d+)?", query)]
    if not minors:
        return None
    return (min(minors), max(minors))


def _summarize_bullets_from_markdown(body: str, limit: int = 8) -> List[str]:
    bullets: List[str] = []
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(("-", "*")):
            item = s.lstrip("-*").strip()
            if item:
                bullets.append(item)
                if len(bullets) >= limit:
                    break
    return bullets


def _maybe_codex_cli_changelog_tldr(query: str, lang: str) -> Optional[str]:
    q = query.lower()
    if "codex" not in q or "cli" not in q:
        return None

    rng = _extract_codex_cli_range(query)
    if not rng:
        return None

    min_minor, max_minor = rng
    if min_minor > max_minor:
        return None

    data = _http_get_json(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "codex-skill-search-web",
        },
    )
    if not isinstance(data, list):
        return None

    releases: Dict[int, Dict[str, Any]] = {}
    for r in data:
        if not isinstance(r, dict):
            continue
        tag = str(r.get("tag_name") or "")
        m = re.fullmatch(r"rust-v0\.(\d{2})\.0", tag)
        if not m:
            continue
        minor = int(m.group(1))
        if min_minor <= minor <= max_minor:
            releases[minor] = r

    if not releases:
        return None

    missing = [m for m in range(min_minor, max_minor + 1) if m not in releases]

    lines: List[str] = []
    lines.append(f"TL;DR: Codex CLI 0.{min_minor:02d}.0 → 0.{max_minor:02d}.0")
    lines.append("")

    for minor in sorted(releases):
        r = releases[minor]
        url = str(r.get("html_url") or f"https://github.com/openai/codex/releases/tag/rust-v0.{minor:02d}.0")
        published = (str(r.get("published_at") or "").split("T")[0]) or "—"
        lines.append(f"0.{minor:02d}.0 ({published}):")
        body = str(r.get("body") or "").strip()
        bullets = _summarize_bullets_from_markdown(body, limit=8)
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
        else:
            lines.append("- (brak szczegółów w opisie release)")
        lines.append(f"  Źródło: {url}")
        lines.append("")

    if missing:
        lines.append("Brak stabilnych wydań w tym zakresie dla: " + ", ".join(f"0.{m:02d}.0" for m in missing))
        lines.append("")

    lines.append("Źródła:")
    lines.append("- https://github.com/openai/codex/releases")
    for minor in sorted(releases):
        url = str(
            releases[minor].get("html_url")
            or f"https://github.com/openai/codex/releases/tag/rust-v0.{minor:02d}.0"
        )
        lines.append(f"- {url}")

    if lang != "pl":
        lines.append("")
        lines.append(f"(Uwaga: lang={lang}; tryb TL;DR obecnie wypisuje po polsku.)")

    return "\n".join(lines).rstrip() + "\n"


def _classify_query(query: str) -> str:
    q = query.strip().lower()
    words = [w for w in re.split(r"\s+", q) if w]
    if len(words) <= 6:
        return "banal"

    complexity_markers = [
        "porówn",
        "różnic",
        "wady",
        "zalety",
        "dlaczego",
        "jak zrobić",
        "krok po kroku",
        "strategi",
        "plan",
        "analiz",
        "relacj",
        "histori",
        "tło",
        "konsekwenc",
        "wpływ",
        "kontrowers",
        "zależy",
    ]
    if any(m in q for m in complexity_markers):
        return "complex"

    if len(words) >= 12:
        return "complex"

    return "banal"


def _explicit_depth_intent(query: str) -> Optional[str]:
    q = query.lower()
    if any(k in q for k in ["3 razy", "trzy razy", "iterac", "seria wyszuka", "zgłębia", "głębok", "deep"]):
        return "deep"
    if any(k in q for k in ["proste", "szybko", "jedno wyszuk", "jednoraz", "basic"]):
        return "simple"
    return None


def _extract_first_json_object(text: str) -> Optional[Dict[str, Any]]:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start : i + 1]
                try:
                    obj = json.loads(chunk)
                except Exception:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def _openrouter_web_search(api_key: str, model: str, query: str, lang: str, max_results: int) -> str:
    prompt = (
        f"Sprawdź w sieci: {query}\n\n"
        f"Wymagania:\n"
        f"- Odpowiedz po {lang} (jeśli użytkownik nie prosi inaczej).\n"
        f"- Streść w 6–12 punktach.\n"
        f"- Dodaj cytowania w tekście w formacie [1], [2]...\n"
        f"- Na końcu dodaj sekcję 'Źródła:' jako listę numerowaną: [n] tytuł — URL.\n"
        f"- Jeśli informacje są rozbieżne, pokaż 2–3 warianty i oznacz cytowaniami.\n"
        f"- Preferuj źródła pierwotne/oficjalne (docs, release notes, GitHub releases) nad blogami i agregatorami.\n"
    )

    payload = {
        "model": model,
        "plugins": [{"id": "web", "max_results": max_results}],
        "messages": [{"role": "user", "content": prompt}],
    }
    data = _request(api_key, payload)
    try:
        return str(data["choices"][0]["message"]["content"])
    except Exception:
        _die(f"Unexpected OpenRouter response schema:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    return ""


def _openrouter_web_search_json_plan(api_key: str, model: str, query: str, lang: str, max_results: int) -> Dict[str, Any]:
    prompt = (
        f"Sprawdź w sieci: {query}\n\n"
        f"Zwróć WYŁĄCZNIE poprawny JSON (bez markdown), w schemacie:\n"
        f"{{\n"
        f"  \"tldr_bullets\": [\"...\"],\n"
        f"  \"sources\": [{{\"title\":\"...\",\"url\":\"...\"}}],\n"
        f"  \"followup_queries\": [\"...\",\"...\"]\n"
        f"}}\n"
        f"Zasady:\n"
        f"- język: {lang}\n"
        f"- 5–10 bulletów\n"
        f"- sources: 3–8 pozycji, preferuj źródła pierwotne/oficjalne\n"
        f"- followup_queries: max 2, bardziej szczegółowe niż startowe\n"
    )
    payload = {
        "model": model,
        "plugins": [{"id": "web", "max_results": max_results}],
        "messages": [{"role": "user", "content": prompt}],
    }
    data = _request(api_key, payload)
    try:
        content = str(data["choices"][0]["message"]["content"])
    except Exception:
        _die(f"Unexpected OpenRouter response schema:\n{json.dumps(data, indent=2, ensure_ascii=False)}")

    obj = _extract_first_json_object(content) or {}
    if not isinstance(obj, dict):
        obj = {}
    obj.setdefault("tldr_bullets", [])
    obj.setdefault("sources", [])
    obj.setdefault("followup_queries", [])
    return obj


def _deep_search_3x(api_key: str, model: str, query: str, lang: str, max_results: int) -> str:
    step1 = _openrouter_web_search_json_plan(api_key, model, query, lang, max_results)
    followups = step1.get("followup_queries") or []
    q2 = str(followups[0]) if len(followups) >= 1 else f"{query} szczegóły"
    q3 = str(followups[1]) if len(followups) >= 2 else f"{query} kontekst i źródła"

    step2 = _openrouter_web_search_json_plan(api_key, model, q2, lang, max_results)
    step3 = _openrouter_web_search_json_plan(api_key, model, q3, lang, max_results)

    sources: List[Dict[str, str]] = []
    seen_urls: set[str] = set()
    for step in (step1, step2, step3):
        for s in step.get("sources") or []:
            if not isinstance(s, dict):
                continue
            url = str(s.get("url") or "").strip()
            title = str(s.get("title") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            sources.append({"title": title or url, "url": url})

    numbered_sources = "\n".join([f"[{i+1}] {s['title']} — {s['url']}" for i, s in enumerate(sources[:12])])
    synthesis_prompt = (
        f"Zsyntetyzuj odpowiedź na pytanie użytkownika: {query}\n\n"
        f"Masz wyniki trzech iteracji researchu (poniżej). Zrób finalny skrót:\n"
        f"- język: {lang}\n"
        f"- 6–12 punktów\n"
        f"- cytowania w tekście w formacie [n] odnoszące się do listy 'Źródła' poniżej\n"
        f"- jeśli są rozbieżności, pokaż 2–3 warianty i oznacz cytowaniami\n\n"
        f"Iteracja 1 (JSON): {json.dumps(step1, ensure_ascii=False)}\n\n"
        f"Iteracja 2 (JSON): {json.dumps(step2, ensure_ascii=False)}\n\n"
        f"Iteracja 3 (JSON): {json.dumps(step3, ensure_ascii=False)}\n\n"
        f"Źródła:\n{numbered_sources}\n"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": synthesis_prompt}],
    }
    data = _request(api_key, payload)
    try:
        return str(data["choices"][0]["message"]["content"]).rstrip() + "\n"
    except Exception:
        _die(f"Unexpected OpenRouter response schema:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Web search + summary via OpenRouter Web plugin (prints assistant content)."
    )
    parser.add_argument("--query", required=True, help="What to search for.")
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="How many web results the plugin can use (1-10 recommended).",
    )
    parser.add_argument(
        "--model",
        default="google/gemini-2.5-flash-lite",
        help="OpenRouter model id.",
    )
    parser.add_argument(
        "--lang",
        default="pl",
        help="Language code used in the prompt (default: pl).",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "simple", "deep"],
        default="auto",
        help="Search strategy: auto (default), simple (1 pass), deep (3 passes).",
    )
    args = parser.parse_args()

    if args.max_results < 1 or args.max_results > 20:
        _die("--max-results must be between 1 and 20")

    codex_tldr = _maybe_codex_cli_changelog_tldr(args.query, args.lang)
    if codex_tldr:
        print(codex_tldr)
        return

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        _die("Missing OPENROUTER_API_KEY in environment.")

    mode = args.mode
    if mode == "auto":
        explicit = _explicit_depth_intent(args.query)
        if explicit:
            mode = explicit
        elif _classify_query(args.query) == "complex":
            print(
                "To wygląda na pytanie średnie/trudne. Wybierz tryb wyszukiwania:\n\n"
                "a) Proste wyszukanie (1 raz) — odpisz: `proste` albo uruchom z `--mode simple`\n"
                "b) Seria 3 wyszukań (zgłębianie) + synteza — odpisz: `seria` albo uruchom z `--mode deep`\n"
            )
            return
        else:
            mode = "simple"

    if mode == "deep":
        print(_deep_search_3x(api_key, args.model, args.query, args.lang, args.max_results))
        return

    # simple
    print(_openrouter_web_search(api_key, args.model, args.query, args.lang, args.max_results).rstrip() + "\n")


if __name__ == "__main__":
    main()
