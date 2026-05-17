# Security Policy

## Supported Versions

Security fixes target the current `main` branch.

## API Key Handling

Paperford is designed to run locally. API requests are sent directly from the user's machine to the configured LLM provider or proxy endpoint.

API keys are kept in the current browser page memory and are not intentionally persisted by Paperford. Do not put API keys in source files, screenshots, issue reports, or pull requests.

Custom Provider Base URLs are user controlled. Only enter trusted endpoints, because the API key will be sent to that endpoint for model fetching, health checks, glossary extraction, and translation jobs.

## Reporting a Vulnerability

If you find a vulnerability, please open a private security advisory on GitHub when available, or contact the maintainer without posting exploit details publicly.

Please include:

- A short description of the issue.
- Steps to reproduce with non-sensitive sample data.
- The affected commit or release, if known.
- Any suggested mitigation.

Do not include real API keys, private EPUB files, or private provider endpoints.
