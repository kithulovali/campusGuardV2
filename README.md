# CampusGuard Backend

Backend-only FastAPI service for campus access control and security monitoring.

## Structure

```text
campusGuardV2/
├── api/v1/
│   ├── endpoints/
│   ├── routers/
│   └── router.py
├── core/
├── db/
├── models/                 # One SQLAlchemy model per file
├── repositories/
├── schemas/
├── services/
├── utils/
├── .env.example
├── main.py
├── requirements.txt
└── seed.py
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The application loads the repository-level `.env` with `python-dotenv` before reading configuration. Set a random `SECRET_KEY` of at least 32 characters and provide either a Turso URL or the MySQL connection variables. Never commit `.env` or real credentials.

## Turso / libSQL

Set `DATABASE_URL` in `.env`:

```text
sqlite+libsql://campusguard-kithulovali.aws-us-east-2.turso.io?secure=true&authToken=YOUR_TURSO_AUTH_TOKEN
```

The SQLAlchemy libSQL dialect is provided by `sqlalchemy-libsql`. When `DATABASE_URL` is empty, the application uses the MySQL settings.

## Run

```bash
uvicorn main:app --reload --port 8000
```

API documentation: `/docs`; API prefix: `/api/v1`.

Use Alembic migrations for existing databases. Development `create_all()` only bootstraps missing tables; it does not alter existing Turso schemas.
