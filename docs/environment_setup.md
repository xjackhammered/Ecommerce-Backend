# Environment Configuration & Local Tunnel Setup

This document covers every environment variable, how to get real values for
the payment providers, and how local tunneling (ngrok / Stripe CLI) is wired
up for webhook and callback testing.

## 1. Environment variables

Copy `.env.example` to `.env` and fill in real values:

```bash
cp .env.example .env
```

| Variable | Where it's used | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django | Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` — never reuse the placeholder in `.env.example`. |
| `DJANGO_DEBUG` | Django | `True` for local/dev, `False` for anything public-facing. |
| `ALLOWED_HOSTS` | Django | Comma-separated. Must include any ngrok host you're actively using, or Django rejects the request with `DisallowedHost`. |
| `POSTGRES_*` | `config/settings.py` | Under Docker Compose these are already correct — `db` is the compose service name, and compose provisions the database/user from these same values. Running Postgres yourself outside Docker: set `POSTGRES_HOST=localhost`. |
| `REDIS_URL` | Category-tree cache | `redis://redis:6379/1` under Docker Compose, `redis://localhost:6379/1` if running Redis natively. |
| `CORS_ALLOWED_ORIGINS` | `django-cors-headers` | Comma-separated list of frontend origins allowed to call the API from a browser. Defaults already cover common local dev ports (Vite 5173, CRA 3000, a plain static server on 5500). |
| `STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` | Stripe SDK | From the Stripe dashboard, **test mode** (`sk_test_...` / `pk_test_...`). No approval process — self-serve signup at https://dashboard.stripe.com/register. |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signature verification | See section 3 below — differs depending on whether you use the Stripe CLI or a dashboard endpoint. |
| `BKASH_BASE_URL` | bKash sandbox | Fixed value, don't change until going to production: `https://tokenized.sandbox.bka.sh/v1.2.0-beta`. |
| `BKASH_APP_KEY` / `BKASH_APP_SECRET` / `BKASH_USERNAME` / `BKASH_PASSWORD` | bKash tokenized checkout auth | bKash's sandbox is open to all developers with no merchant onboarding required — see bKash's own developer docs. This project uses bKash's publicly documented shared sandbox credentials (see `.env.example`); a dedicated merchant sandbox application is optional and only needed before going to production. |
| `BKASH_CALLBACK_URL` | bKash checkout creation | Where the user's **browser** is redirected after approving/declining payment on bKash's hosted page. See section 4 — this can be `http://localhost:8000/...` and does not require ngrok. |

## 2. Docker Compose

```bash
docker compose up -d
docker compose exec backend python manage.py seed_data
```

If port 5432 is already taken by a locally-installed Postgres, either stop
that service (`sudo systemctl stop postgresql`) or remap the container's
published port in `docker-compose.yml` (`"5433:5432"` instead of
`"5432:5432"` — this only affects the host-side port, the `backend`
container still talks to `db` internally on 5432).

If `docker compose` reports a permission error connecting to the daemon
socket, your shell session hasn't picked up the `docker` group yet:
`sudo usermod -aG docker $USER`, then `newgrp docker` (or log out/in).

## 3. Stripe webhook — two ways to receive events locally

### Option A — Stripe CLI (recommended for local development)

No public URL needed at all:

```bash
stripe login
stripe listen --forward-to localhost:8000/api/payments/stripe/webhook/
```

Copy the `whsec_...` value it prints into `STRIPE_WEBHOOK_SECRET`, restart
the backend. Keep `stripe listen` running in its own terminal while testing.

### Option B — Dashboard endpoint (needs ngrok)

```bash
ngrok http 8000
```

In the Stripe dashboard (**test mode**) → Developers → Webhooks → Add
endpoint → URL: `https://<ngrok-id>.ngrok-free.app/api/payments/stripe/webhook/`
→ select `payment_intent.succeeded` and `payment_intent.payment_failed`.
Copy the endpoint's signing secret into `STRIPE_WEBHOOK_SECRET`.

Each time ngrok restarts (free tier = new URL every time), update: the
dashboard endpoint URL, and `ALLOWED_HOSTS` in `.env`. The signing secret
does not change unless you delete and recreate the endpoint.

## 4. bKash callback — no tunnel required

Unlike Stripe's webhook (Stripe's servers calling your backend directly,
which needs a real public URL), bKash's callback is a **browser-side
redirect** — after the user approves payment on bKash's hosted checkout
page, that page redirects the user's own browser to `BKASH_CALLBACK_URL`.
Since the browser and the backend are on the same machine during local
testing, this works over plain `localhost`:

```
BKASH_CALLBACK_URL=http://localhost:8000/api/payments/bkash/callback/
```

No ngrok needed for this leg. (If your bKash sandbox setup requires the
callback URL to be pre-registered in the developer portal, use whatever
URL you register there — `localhost` has worked without issue in testing
for this project.)

## 5. Verifying it all works

```bash
# Stripe token grant / API reachability
docker compose exec backend python manage.py shell -c "
import stripe
from django.conf import settings
stripe.api_key = settings.STRIPE_SECRET_KEY
print(stripe.PaymentIntent.list(limit=1))
"

# bKash token grant
docker compose exec backend python manage.py shell -c "
from apps.payments.strategies import BkashStrategy
print(BkashStrategy()._get_token())
"
```

Both should print a real response (a Stripe list object, or a bKash token
string) with no exception. From there, run a full order → checkout →
confirm cycle through the API or the frontend for each provider — see the
[payment flow diagrams](payment_flow.md) for the exact sequence.