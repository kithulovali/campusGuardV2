# CampusGuard

CampusGuard is a backend-first campus access-control and security monitoring API. The React client is maintained separately and is not part of the backend architecture or deployment on this branch.

## Backend stack

- FastAPI with versioned REST endpoints under `/api/v1`
- SQLAlchemy 2.x typed declarative mappings and `select()` statements
- Pydantic v2 request/response validation
- Repository layer for persistence queries
- Service layer for application and business rules
- Router layer for HTTP contracts and dependency injection
- MySQL through PyMySQL
- JWT access and refresh tokens

## Backend structure

```text
CampusGuard/
  app/
    api/v1/
      routers/       # HTTP endpoints
      endpoints/     # Feature endpoints being migrated into routers
    core/             # Settings, security, authorization
    db/               # Engine, session and declarative base
    models/           # SQLAlchemy ORM models
    repositories/     # SQLAlchemy persistence operations
    schemas/          # Pydantic v2 contracts
    services/         # Application/business logic
    utils/
  main.py
  requirements.txt
```

## Configuration

Copy `.env.example` to `.env` inside `CampusGuard/`. Set either `DATABASE_URL` or the individual database variables. Set a unique random `SECRET_KEY` with at least 32 characters. Never commit `.env`.

## Run locally

```bash
cd CampusGuard
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs`. API routes are under `/api/v1`.

Database schema changes should be delivered as Alembic migrations. Automatic `create_all` is enabled only in development; production must apply migrations before deployment.

## Branch scope

The `master` branch is the isolated backend refactor. It does not modify `CampusGuard-web/`, configure CORS for a frontend, or depend on the React application. The legacy gate, visitor, and reporting feature modules are being migrated into the repository/service/router pattern incrementally; do not treat the branch as a completed production migration until those modules and integration tests are converted.
