# Paperford

**Local EPUB bilingual translator for cleaner long-form reading copies.**

[中文说明](README_ZH.md)

![Python](https://img.shields.io/badge/Python-3.10--3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-local%20backend-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React%20%2B%20Vite-web%20UI-61DAFB?logo=react&logoColor=111)
![License](https://img.shields.io/badge/License-MIT-111111)

Paperford is a local EPUB translation workbench. It parses long books into controlled text blocks, translates them through an OpenAI-compatible API, and creates bilingual EPUB files with the source text and translation interleaved.

It is built for people who want more control than a raw machine-translation pass: glossary terms, translation profiles, style presets, continuity context, cache reuse, failed-block retry, and a clear local privacy boundary.

![Paperford home screen](docs/assets/paperford-home.png)

## What It Does

| Area | What you get |
| --- | --- |
| EPUB workflow | Upload an EPUB, preview extracted text, translate, and download a bilingual EPUB. |
| Translation control | Choose Fast Draft, Balanced, or Refine profiles plus literary, faithful, web-novel, and nonfiction styles. |
| Terminology | Auto-extract names and proper nouns from front/middle/back samples, then keep glossary terms consistent. |
| Reliability | Split long blocks before translation, validate JSON output, retry failed blocks, and cache repeated work in SQLite. |
| Privacy | Files stay on your machine. API keys live only in current page memory and are sent only to your configured provider. |

## Highlights

- One-command local web app: FastAPI backend, React/Vite frontend, served at `http://127.0.0.1:8000`.
- OpenAI-compatible providers: OpenAI, DeepSeek, xAI, Gemini-compatible endpoints, and custom Base URLs.
- Bilingual EPUB output that keeps the original book structure and inserts translations after matching text blocks.
- Translation profiles for speed/quality tradeoffs: Fast Draft, Balanced, and Refine.
- Built-in style presets for literary prose, faithful translation, web novels, and nonfiction.
- SQLite translation cache keyed by text, model, language, prompt version, profile, style, and glossary.
- Progress dashboard with speed, ETA, cache hits, failed blocks, and average batch time.

![Paperford progress and settings](docs/assets/paperford-progress-settings.png)

## Quick Start

```bash
git clone https://github.com/zommmo/paperford.git
cd paperford
./run_web.sh
```

Then open:

```text
http://127.0.0.1:8000
```

`run_web.sh` prepares the Python virtual environment, installs dependencies, builds the frontend with Vite, and starts the local FastAPI server. On macOS, if Homebrew `node@22` is available, the script prefers it.

## Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
.venv/bin/python -m uvicorn api_app:app --host 127.0.0.1 --port 8000
```

## Workflow

1. Enter your API key in the settings panel.
2. Choose a provider, or add a session-only custom provider.
3. Enter a model name, or click Fetch Models.
4. Upload an EPUB and optionally parse a preview first.
5. Choose the translation profile, style preset, target language, temperature, batch size, concurrency, and max block count.
6. Optionally auto-extract terms, or maintain the global glossary manually.
7. Start translation and download the bilingual EPUB when complete.
8. Clear the translation cache from the debug section when you want fresh translations.

## Translation Controls

Paperford separates style instructions, glossary terms, continuity context, and strict JSON output constraints so custom prompts do not break structured model output.

Translation profiles:

- **Fast Draft**: larger processing windows and less context for quick, lower-cost drafts.
- **Balanced**: the default profile, balancing context, speed, and natural prose.
- **Refine**: smaller windows plus an extra polish pass for reading copies where style matters more.

Style presets:

- **Literary Natural**: preserve voice, rhythm, imagery, and dialogue flow.
- **Faithful**: stay close to source meaning, sequence, and detail without embellishment.
- **Web Novel**: direct, readable, energetic genre-fiction prose.
- **Nonfiction**: precise terminology, clear logic, and low-ornament prose.

## Automatic Glossary

Auto-extract terms does not send the entire book to the model. It samples roughly `18000` characters across the front, middle, and back of the source text, then asks the model to identify main characters, locations, factions, organizations, and proper nouns.

Glossary format:

```text
Alice=Alice
King's Landing=King's Landing
Silver City=Silver City
```

Glossary content is included in the cache key. Changing glossary terms creates separate cache entries instead of reusing older translations.

## Output and Cache

- Generated EPUB files are written to `output/` and are also available through the download button.
- The translation cache is stored in `translations.sqlite3`.
- Cache keys include text hash, model, prompt version, target language, temperature, Thinking mode, translation profile, style preset, custom style prompt hash, and glossary hash.

## Safety Notes

- Uploaded files must be `.epub`, non-empty, and no larger than 100MB by default.
- Translation parameters are validated on the backend: temperature `0-2`, batch size `1-50`, concurrency `1-20`, max blocks `0-200000`.
- API keys are kept only in current page memory and are lost after refresh.
- A custom Provider Base URL receives the API key you enter. Only use trusted LLM providers or proxy endpoints you control.
- Thinking mode is off by default. Enable it only when the selected model/provider supports it.

## Development Checks

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
cd frontend && npm run build
cd frontend && npm audit --audit-level=moderate
```

GitHub Actions runs backend tests and frontend builds on pushes and pull requests. CodeQL and Dependabot provide baseline security scanning and dependency update coverage.

## Current Limitations

- Only one EPUB can be processed at a time.
- Custom providers are stored only in the current page session and disappear after refresh.
- Text extraction currently covers `h1-h6`, `p`, and `li` tags.
- Failed blocks can be retried; downloaded EPUBs created before retry still use `[untranslated]` placeholders.

## License

MIT License
