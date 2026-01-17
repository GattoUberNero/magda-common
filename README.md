# magda-common

Małe publiczne repo do propagacji lokalnych dodatków (np. skilli do Codex CLI) między maszynami przez `git clone`.

## Skills (Codex CLI)

Skille są w `skills/`.

Aktualnie:
- `skills/search-web` — web research przez OpenRouter (z trybem 3× pogłębiania) + szybki TL;DR dla changelogów Codex CLI z GitHub Releases.

### Instalacja skilla (ręcznie)

Przykład dla `search-web`:

```bash
git clone git@github.com:GattoUberNero/magda-common.git
mkdir -p ~/.codex/skills
cp -a magda-common/skills/search-web ~/.codex/skills/search-web
```

### Instalacja skilla (skrypt)

```bash
git clone git@github.com:GattoUberNero/magda-common.git
cd magda-common
./install-skill.sh search-web
```

## Wymagania

- `search-web` używa OpenRouter: ustaw `OPENROUTER_API_KEY` w środowisku.
- Jeśli trzymasz klucze w `~/.bashrc`, upewnij się, że są ładowane także w trybie nieinteraktywnym (albo przenieś do `~/.profile` / `~/.bash_profile`).
