# E-commerce Ordering & Payment System

Backend for user management, product catalog, orders, and multi-provider
payments (Stripe + bKash), built with Django + Django REST Framework.

Built for the Raco AI Technologies backend engineer assessment.

## Docs

- [Architecture](docs/architecture.md) — layering, strategy pattern, DFS + caching, stock algorithm
- [ERD](docs/ERD.md) — table schema and relationships
- [Payment flow diagrams](docs/payment_flow.md) — Stripe & bKash sequence diagrams
- [API reference](docs/api.md) — endpoints + curl examples (Swagger UI at `/api/docs/`)

## Tech stack

- Django 5 + Django REST Framework
- PostgreSQL, Redis (category-tree cache)
- SimpleJWT for authentication
- Stripe SDK, bKash Tokenized Checkout (sandbox) via `requests`
- drf-spectacular for auto-generated OpenAPI/Swagger docs
- Docker + docker-compose for local/staging deployment

## Local setup (without Docker)

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env: fill in your Stripe test keys and bKash sandbox credentials.
# For local Postgres/Redis running on your machine, set:
#   POSTGRES_HOST=localhost
#   REDIS_URL=redis://localhost:6379/1

python manage.py migrate
python manage.py seed_data       # creates admin@example.com / Admin@12345 + sample catalog
python manage.py runserver
```

API is now at `http://localhost:8000/api/`, docs at `http://localhost:8000/api/docs/`.

## Docker setup

```bash
cp .env.example .env
# fill in real values, keep POSTGRES_HOST=db and REDIS_URL as-is (compose sets them)

docker compose up --build
docker compose exec backend python manage.py seed_data
```

## Exposing the backend for Stripe/bKash webhooks (ngrok)

Both Stripe webhooks and the bKash callback need a public HTTPS URL that
reaches your locally-running backend:

```bash
ngrok http 8000
```

Then:
- Set your Stripe webhook endpoint (in the Stripe dashboard, test mode) to
  `https://<ngrok-id>.ngrok-free.app/api/payments/stripe/webhook/`, listening
  for `payment_intent.succeeded` and `payment_intent.payment_failed`. Copy
  the signing secret into `STRIPE_WEBHOOK_SECRET` in `.env`.
- Set `BKASH_CALLBACK_URL` in `.env` to
  `https://<ngrok-id>.ngrok-free.app/api/payments/bkash/callback/`.

## Frontend

This repo is backend-only. A frontend (if you build one) deploys to Vercel
and points `NEXT_PUBLIC_API_URL` / equivalent at your ngrok URL during
review, or at your real backend host in production.

## Running tests

The test suite runs against SQLite in-memory so it needs no external
services:

```bash
DJANGO_SETTINGS_MODULE=config.settings python manage.py test
```

(Or point `DATABASES` at SQLite in a throwaway settings override if you
don't have Postgres running locally — see comments in `config/settings.py`.)

Test coverage:
- **Unit tests** for every domain service: `UserService`, `ProductService`
  (stock-reduction race safety), `CategoryTreeService` (DFS + cache
  invalidation), `OrderService` (deterministic totals), `PaymentService`
  (strategy dispatch, success/failure/webhook paths) — using a `FakeStrategy`
  so no real network calls happen during tests.
- **API tests** (`tests/test_api.py`) for registration/login, order
  creation and ownership isolation, the full checkout → confirm flow, and
  the bKash callback endpoint.

## Design pattern & algorithm summary (for reviewers)

| Requirement | Where |
|---|---|
| OOP classes | `apps/*/services.py` — `UserService`, `ProductService`, `CategoryTreeService`, `OrderService`, `PaymentService` |
| Deterministic total/subtotal algorithm | `OrderService.create_order` |
| Safe stock reduction | `ProductService.reduce_stock` (row lock + conditional update) |
| Strategy pattern | `apps/payments/strategies.py` (`PaymentStrategy`, `StripeStrategy`, `BkashStrategy`) + `PaymentService` as context |
| DFS traversal | `CategoryTreeService._build_tree` / `get_descendant_ids` |
| Redis caching | `CategoryTreeService.get_tree` (cached, invalidated via Django signals) |
