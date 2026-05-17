# AI Handoff

Updated: 2026-05-17

## Project

Paperford is a local FastAPI + React app for translating EPUB books into bilingual, interleaved EPUB files. The public GitHub repository is `zommmo/paperford`.

## Current Security and GitHub Setup

- GitHub Actions CI runs Python `unittest` and the frontend Vite build on push and pull request.
- CodeQL is configured for Python and JavaScript/TypeScript.
- Dependabot checks pip, npm, and GitHub Actions weekly.
- `SECURITY.md`, `CONTRIBUTING.md`, issue templates, and a pull request template are present.
- Secret scanning and push protection are enabled on GitHub.

## Backend Safety Limits

- EPUB uploads are rejected unless the filename ends in `.epub`.
- Empty uploads are rejected.
- Uploads over 100MB are rejected by the API layer.
- Translation parameters are bounded:
  - `temperature`: `0` to `2`
  - `batch_size`: `1` to `50`
  - `concurrency`: `1` to `20`
  - `max_blocks`: `0` to `200000`

## Key Runtime Behavior

- API keys are accepted from the browser and kept in process memory only for the current job.
- Custom Provider Base URLs are user controlled; the API key is sent to that endpoint for model fetching, health checks, glossary extraction, and translation.
- Translation cache is SQLite in `translations.sqlite3`.
- Generated EPUB files are written to `output/`.

## Verification

Use:

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
cd frontend && npm run build
cd frontend && npm audit --audit-level=moderate
```

## Notes for Future Agents

- Do not commit `.venv`, `frontend/node_modules`, `frontend/dist`, `translations.sqlite3`, `output/`, `.env`, or private EPUB files.
- If prompt behavior, glossary behavior, target language, or translation parameters change, review cache key behavior.
- Keep Chinese and English README files in sync for user-facing features.
