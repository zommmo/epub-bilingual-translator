# Paperford - Local EPUB Bilingual Translator

[中文说明](README.md)

Paperford is a local EPUB translation workbench. It parses long-form EPUB books into controlled text blocks, translates them through an OpenAI-compatible API, and generates bilingual EPUB copies with the original text and translation interleaved.

The goal is not a rough machine-translation dump. Paperford gives you more editorial control over long-form translation: glossary terms, translation profiles, style presets, continuity context, caching, failed-block retry, and a clear local privacy boundary.

![Paperford home screen](docs/assets/paperford-home.png)

## Why the name Paperford

Paperford combines "paper" and "ford": a local tool for carrying a book from one language to another. To make the repository easier to understand at a glance, the public project name is now presented as:

**Paperford - Local EPUB Bilingual Translator**

## Highlights

- Local web app: FastAPI backend and React/Vite frontend, started with one script.
- Bilingual EPUB output: preserve the source structure and insert translations after the matching text blocks.
- OpenAI-compatible APIs: works with OpenAI, DeepSeek, xAI, Gemini-compatible endpoints, and custom Base URLs.
- Translation quality controls: Fast Draft, Balanced, and Refine profiles with literary, faithful, web-novel, and nonfiction style presets.
- Automatic glossary extraction: sample the front, middle, and back of a book to identify characters, locations, factions, and proper nouns.
- Long-block handling: estimate token size, split long passages before translation, and merge the results back into the original paragraph.
- Local cache: SQLite avoids repeated requests for the same text and settings.
- Progress dashboard: speed, ETA, batch latency, cache hits, and failures.
- Clear privacy model: EPUB files stay on your machine; API keys are kept only in current page memory.

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
