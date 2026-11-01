# CampusGuard Backend

Backend-only FastAPI service for campus access control and security monitoring. The frontend is intentionally excluded from this branch.

## Stack

- FastAPI and Pydantic v2
- SQLAlchemy 2.x
- SQLite through Turso/libSQL, or MySQL through PyMySQL
- Alembic for schema migrations
- Repository, service, and router layers
- JWT access and refresh tokens

## Project structure

```text
campusGuardV2/
├── app/
│   ├── api/v1/
│   │   ├── endpoints/    # Existing feature endpoints
│   │   └── routers/      # Refactored auth and user routers
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   └── utils/
├── .env.example
├── main.py
├── requirements.txt
└── seed.py
```

## Configure Turso

Install dependencies and copy the environment template:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `DATABASE_URL` in `.env` to the SQLAlchemy libSQL dialect URL. For the database host supplied for this project, the format is:

```text
sqlite+libsql://campusguard-kithulovali.aws-us-east-2.turso.io?secure=true&authToken=YOUR_TURSO_AUTH_TOKEN
```

Generate a database authentication token in the Turso dashboard/CLI and replace the placeholder locally. Do not commit the token or the real `.env` file. The dependency `sqlalchemy-libsql` provides the SQLAlchemy dialect and its libSQL client dependency. The application already reads `DATABASE_URL`; if it is unset, it falls back to the MySQL settings.

## Run

```bash
uvicorn main:app --reload --port 8000
```

API documentation: `http://localhost:8000/docs`. API routes are prefixed with `/api/v1`.

## Database migrations

Use Alembic for schema changes. `Base.metadata.create_all()` is retained only as a development bootstrap for a new local database; it does not upgrade an existing Turso database. Apply reviewed migrations before deploying schema changes.

## Scope

This branch contains the backend only. The React frontend directory has been removed from this branch; the original `main` branch remains unchanged. Some legacy gate, visitor, and reporting feature endpoints still require migration into the repository/service/router pattern and automated integration testing before production readiness.
