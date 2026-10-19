# Codex working agreement

## Architecture

- Keep one FastAPI backend in `backend/app/`; build features as modules inside it when needed.
- Keep React in `frontend/` and project decisions in `docs/`.
- PostgreSQL schema and Alembic live in `backend/app/db/` and `backend/alembic/`. Do not add unused layers or abstractions.
- `/health` currently checks only that the API process responds.

## Code

- Target Python 3.11+ and use type hints for new functions.
- Keep route handlers and modules small and named for business concepts.
- Run Ruff lint and format checks. Add dependencies to `pyproject.toml` only when used.
- Keep money as `Decimal`/`NUMERIC`; use one `session.begin()` for a business write and stable idempotency keys for payments and stock events.
- Keep auth in `backend/app/auth/`. Passwords use Argon2; signing keys come from environment; refresh token hashes and revocation state live in PostgreSQL.
- Follow the existing layout before adding new directories or patterns.

## Testing

- Add focused Pytest tests for behavior changed by a task.
- Run `python -m ruff check .`, `python -m ruff format --check .`, and `python -m pytest` before reporting completion.
- State what was actually run and any checks that could not run.

## Security

- Never commit `.env`, credentials, tokens, or real customer data.
- Review generated Alembic revisions; never run destructive migrations against an existing database automatically.
- Use environment variables for secrets; `.env.example` contains placeholders only.
- Validate external input and use parameterized database queries when database access is added.
- Do not log secrets or sensitive personal data.
- Check active sessions and current roles on protected requests. Return 401 for invalid credentials and 403 for authenticated users without permission.

## Codex workflow

- Inspect existing code and Git status before editing; preserve user changes.
- Make the smallest change that meets the current task. Explain design choices and verification.
- Do not push, publish, or move to a later task without the user's instruction.
- Ask only when a choice cannot be inferred safely; otherwise proceed and document assumptions.

