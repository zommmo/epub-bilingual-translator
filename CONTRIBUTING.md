# Contributing

Thanks for improving Paperford.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
```

## Run the App

```bash
./run_web.sh
```

Open `http://127.0.0.1:5173`.

## Verification Before a Pull Request

Run Python tests:

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Security and Privacy

- Do not commit API keys, `.env` files, generated EPUB files, SQLite cache files, or private books.
- Be careful with custom Provider Base URLs. API keys are sent to the configured endpoint.
- If a change affects prompts, target languages, glossary handling, or translation parameters, check whether cache keys need to change.

## Pull Request Notes

- Keep changes focused.
- Include tests for backend behavior changes.
- Update both Chinese and English README files when changing user-facing behavior.
