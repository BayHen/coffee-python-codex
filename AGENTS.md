# Codex working agreement

## Architecture

- Keep one FastAPI backend in `backend/app/`; build features as modules inside it when needed.
- Keep React in `frontend/` and project decisions in `docs/`.
- PostgreSQL integration belongs to a later task. Do not add unused layers or abstractions.
- `/health` currently checks only that the API process responds.

## Code

- Target Python 3.11+ and use type hints for new functions.
- Keep route handlers and modules small and named for business concepts.
- Run Ruff lint and format checks. Add dependencies to `pyproject.toml` only when used.
- Follow the existing layout before adding new directories or patterns.

## Testing

- Add focused Pytest tests for behavior changed by a task.
- Run `python -m ruff check .`, `python -m ruff format --check .`, and `python -m pytest` before reporting completion.
- State what was actually run and any checks that could not run.

## Security

- Never commit `.env`, credentials, tokens, or real customer data.
- Use environment variables for secrets; `.env.example` contains placeholders only.
- Validate external input and use parameterized database queries when database access is added.
- Do not log secrets or sensitive personal data.

## Codex workflow

- Inspect existing code and Git status before editing; preserve user changes.
- Make the smallest change that meets the current task. Explain design choices and verification.
- Do not push, publish, or move to a later task without the user's instruction.
- Ask only when a choice cannot be inferred safely; otherwise proceed and document assumptions.

