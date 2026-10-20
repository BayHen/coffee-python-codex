# Testing and security report

Audit date: 2026-10-20

## Strategy

The test strategy follows the business transaction boundaries rather than individual implementation methods:

1. Validate request schemas and reject extra or malformed input.
2. Verify authentication lifecycle, active sessions, refresh rotation, logout, disabled accounts, and 401/403 separation.
3. Verify RBAC at HTTP endpoints and again at AI tool execution.
4. Exercise order totals, state transitions, snapshots, payment idempotency, and concurrent payment attempts against PostgreSQL.
5. Exercise inventory ledger direction, non-negative stock, order consumption, cancellation returns, idempotency, and concurrent outflow.
6. Reconcile reporting aggregates against seeded succeeded, failed, refunded, and cancelled payments.
7. Treat AI as an untrusted interpreter: fake the provider, validate output, allowlist tools, reject invented SQL tools, and never run external calls in the default suite.
8. Test frontend login, in-memory token handling, refresh behavior, RBAC visibility, POS workflow, AI chat, lint, type checking, and production build.

All database integration and concurrency tests require a migrated database ending in `_test`. No destructive test was run against the development database.

## Test matrix

| Area | Unit/schema | API integration | PostgreSQL/concurrency | Frontend |
| --- | --- | --- | --- | --- |
| Authentication | JWT, password, limiter | login, refresh rotation, logout, inactive users, 401/403 | session row locks and token hash | login, 401 refresh, tokens absent from browser storage |
| Catalog | validation, Decimal prices | CRUD, RBAC, conflicts, injection payload | uniqueness constraints | product CRUD workflow |
| Orders/payments | totals, discount, state machine | snapshots, idempotency, invalid transitions | two concurrent successful payments produce one record | POS and order payment workflow |
| Inventory | units, movement direction | CRUD, recipes, ledger, idempotency, cancellation | two outflows cannot create negative stock | inventory listing and movement form |
| People/loyalty | validation and points rules | CRUD, history, RBAC, award/refund idempotency | uniqueness and ledger constraints | no dedicated page yet |
| Reporting | timezone/date rules | exact totals, refunds, cancelled exclusion, Staff denial | real aggregation queries | date filter and real charts |
| AI | output schema and tool arguments | service orchestration with mocked OpenAI | existing read-only services only | Manager chat workflow and Staff-hidden navigation |
| HTTP policy | CORS parser, security headers | response headers | not applicable | same-origin API client |

## Confirmed findings and fixes

### High

**SEC-01 — Login had no failed-attempt limit — Fixed.** An attacker could repeatedly test passwords. A hashed client-host/email key now permits ten failures per five minutes and returns HTTP 429 with `Retry-After`. Successful login clears the counter. The limiter deliberately does not store raw email addresses.

### Medium

**SEC-02 — CORS deployment policy was implicit — Fixed.** Same-origin was safe, but a split frontend deployment had no explicit policy. `CORS_ALLOWED_ORIGINS` now accepts only concrete HTTP(S) origins, rejects `*`, disables credentialed CORS, and limits methods and headers.

**QA-01 — Customer history response failed under Pydantic v2 — Fixed.** `CustomerOrderView` now enables `from_attributes`, restoring the real API integration test.

**QA-02 — Inventory concurrency test fixture exceeded `roles.name` length — Fixed.** The randomized suffix now stays within the actual schema, allowing the stock race test to execute.

### Low

**SEC-03 — Security response headers were absent — Fixed.** API responses now include `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`. Auth, AI, and report responses receive `Cache-Control: no-store`.

**SEC-04 — Auth request models accepted unknown fields — Fixed.** Login, refresh, user creation, and status update schemas now use `extra="forbid"`.

**SEC-05 — Runtime `assert` guarded two service assumptions — Fixed.** Assertions disappear under optimized Python. They were replaced with explicit, normalized API errors. Bandit now reports zero issues.

## Security review

- SQL access uses SQLAlchemy expressions and bound parameters. No request value is interpolated into SQL. A catalog search test submits `' OR 1=1 --` and receives an empty, valid response.
- Dynamic sort fields use Pydantic literals/enums. Pagination and date ranges have upper bounds.
- Passwords use Argon2. Unknown-user login performs a dummy password verification to reduce account enumeration timing differences.
- Access JWTs require issuer, audience, subject, session, type, timestamps, and a fixed algorithm. Protected requests verify active database sessions and current user/employee state.
- Refresh tokens are opaque, stored only as SHA-256 hashes, rotated under a row lock, and revoked on logout or account disablement.
- The frontend keeps tokens in memory and tests prove they are absent from `localStorage` and `sessionStorage`.
- Orders, payments, inventory, and loyalty use stable idempotency keys plus request fingerprints and database uniqueness constraints.
- Payment and inventory race tests use independent PostgreSQL sessions and row locks.
- Revenue and AI endpoints require Admin or Manager; Staff receives 403.
- AI has three read-only allowlisted tools. It has no SQL, shell, HTTP, purchasing, refund, or database-write capability. Tool arguments and final output are validated, and actual tool names replace model-provided claims.
- `.env` and `.env.*` are ignored except `.env.example`. A tracked-files scan found placeholders only and no committed API keys, tokens, private keys, or passwords.

## Dependency and static analysis

- `npm audit --omit=dev`: zero production vulnerabilities.
- Bandit 1.9.4 over `backend/app`: zero findings after fixes.
- `pip check`: no broken requirements.
- `pip-audit`: application libraries produced no finding; the environment's installer `pip 25.3` produced advisories. `pip` is a development/install tool rather than an application runtime dependency. Upgrade to 26.2.1 was attempted but Windows denied replacement of its own loaded files; recreate the virtual environment or update it from a fresh terminal before deployment packaging.

## Remaining risks

| Severity | Risk | Required deployment action |
| --- | --- | --- |
| Medium | Login and AI rate limits are process-local and do not coordinate multiple workers. | Use Redis or API gateway rate limiting before horizontal scaling. |
| Medium | Proxy/TLS behavior, HSTS, trusted host enforcement, and forwarded client IP handling are environment-specific. | Terminate TLS at a reviewed reverse proxy, configure trusted hosts/proxies, then add HSTS there. |
| Medium | Python dependencies use bounded ranges rather than a reviewed deployment lockfile. | Produce and scan a pinned lock/constraints file in CI. |
| Medium | Real OpenAI integration was not executed because no API key was supplied. | Run a controlled staging smoke test with budget and data-retention settings reviewed. |
| Medium | Customer contact data is visible to Staff by current business policy. | Confirm least-privilege requirements and consider masked list responses. |
| Low | Swagger/ReDoc remain enabled in production. | Disable or protect interactive docs if the deployment threat model requires it. |
| Low | No browser E2E, load, soak, backup-restore, or disaster-recovery test exists. | Add these gates before a production launch. |
| Low | Partial payment refunds are not represented by a separate immutable refund ledger. | Add a refund model before supporting partial refunds. |

No confirmed Critical issue remains in the audited scope. No confirmed High issue remains after the login limiter fix.

## Commands and results

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://coffee_dev@127.0.0.1:55433/coffee_shop_test"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m bandit -r backend/app -q
.\.venv\Scripts\python.exe -m pip check

cd frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd audit --omit=dev
```

Verified result: 71 backend tests passed; 5 frontend tests passed; Ruff, formatting, Bandit, ESLint, TypeScript, Vite build, and npm production dependency audit passed.

## Pre-deployment checklist

- [x] Create a fresh virtual environment and upgrade `pip` to 26.2.1 or later.
- [x] Install from reviewed pinned dependencies and repeat dependency audits.
- [ ] Set strong `JWT_SECRET_KEY`, `DATABASE_URL`, and server-only `OPENAI_API_KEY` in a secrets manager.
- [ ] Set exact production `CORS_ALLOWED_ORIGINS`; never use a wildcard.
- [ ] Configure HTTPS, trusted proxy/host policy, HSTS, request size limits, and centralized rate limits.
- [ ] Run Alembic against a staging backup and verify the current revision.
- [x] Run the complete backend suite against an isolated migrated `_test` database.
- [x] Run frontend tests, lint, and production build.
- [ ] Run a controlled OpenAI staging smoke test and confirm budget/token limits.
- [x] Review Staff access to customer contact data. Staff currently receives phone/email to support POS lookup; production approval of this policy is still required.
- [x] Test backup restoration into an isolated database and verify its Alembic revision.
- [ ] Verify production monitoring and alert delivery.
- [ ] Exercise the rollback plan in staging.

Local verification on 2026-10-20 used pinned lockfiles, produced 71 passing backend tests against PostgreSQL, 5 passing frontend tests, clean Ruff/format/ESLint/build results, zero findings from `pip-audit`, and zero production findings from `npm audit`. The restored database reported Alembic revision `b9d1e3f5a7c2` and 17 public tables.
