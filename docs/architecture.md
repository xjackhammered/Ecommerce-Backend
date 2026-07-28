# System Architecture

## High-level component diagram

```mermaid
flowchart TB
    subgraph Client
        FE[Frontend (Vercel)]
    end

    subgraph Backend [Django + DRF backend - via ngrok]
        API[REST API layer]
        SVC[Domain services\nUserService / ProductService /\nOrderService / PaymentService]
        STRAT[Payment strategies\nStripeStrategy / BkashStrategy]
        API --> SVC
        SVC --> STRAT
    end

    DB[(PostgreSQL)]
    CACHE[(Redis)]
    STRIPE[[Stripe API]]
    BKASH[[bKash Sandbox API]]

    FE -->|HTTPS + JWT| API
    SVC --> DB
    SVC --> CACHE
    STRAT --> STRIPE
    STRAT --> BKASH
    STRIPE -.webhook.-> API
    BKASH -.callback redirect.-> API
```

## Layering

Each domain (`users`, `products`, `orders`, `payments`) follows the same
three-layer split:

1. **Models** (`models.py`) — persistence only: fields, indexes, constraints.
2. **Services** (`services.py`) — the OOP classes required by the
   assessment (`UserService`, `ProductService`, `CategoryTreeService`,
   `OrderService`, `PaymentService`). All business rules — uniqueness
   checks, stock math, total calculation, provider dispatch — live here,
   not in views or serializers. This is what lets the same logic be reused
   from a view, a management command, a webhook handler, or a test without
   duplicating rules.
3. **Views** (`views.py`) — thin DRF views/viewsets that validate input with
   a serializer, call a service method, and serialize the result. Views
   never contain business logic.

`apps/common/` holds cross-cutting concerns: a shared `DomainError`
exception (mapped to clean 400 responses by a custom DRF exception
handler) and an `IsAdminOrReadOnly` permission.

## Strategy pattern (payments)

```
PaymentStrategy (ABC)
    ├── initiate(order, amount) -> transaction_id, status, raw_response, client_payload
    ├── confirm(transaction_id, payload) -> status, raw_response
    └── query(transaction_id) -> status, raw_response

StripeStrategy(PaymentStrategy)   -- wraps the `stripe` SDK
BkashStrategy(PaymentStrategy)    -- wraps bKash's tokenized checkout REST API

PaymentService (context)
    - never imports stripe/bkash directly
    - calls get_strategy(provider) to obtain the right implementation
    - orchestrates: create Payment row -> confirm -> reduce stock -> mark order paid
```

Adding a third provider (e.g. Nagad, SSLCommerz) means writing one new
`PaymentStrategy` subclass and registering it in `STRATEGY_REGISTRY`.
Nothing in `OrderService`, the views, or the `Payment` model needs to
change.

## DFS + Redis caching (category tree)

`CategoryTreeService._build_tree()` loads every category row once, groups
children by `parent_id` in memory, then does a depth-first recursive walk
(`dfs(parent_id)`) to build a nested tree. The result is cached in Redis
under `category_tree:v1` for one hour. A `post_save`/`post_delete` signal
on `Category` invalidates the cache immediately whenever the tree changes,
so stale data is never served for long. `recommend_products()` reuses the
cached tree to find all descendant category ids of a given category (also
via DFS) and returns active products across that whole sub-tree.

## Stock reduction algorithm

`ProductService.reduce_stock()` runs inside a DB transaction, takes a row
lock with `select_for_update()`, and applies a conditional
`UPDATE ... WHERE stock >= quantity`. If two payment confirmations for
different orders race for the same product, only one can succeed — the
second sees `updated == 0` and raises a `DomainError`, guaranteeing stock
can never go negative.

## Order flow (matches the required sequence)

1. `POST /api/orders/` — user selects products, `OrderService.create_order`
   validates stock (without reducing it yet) and computes `subtotal`/`total`
   deterministically.
2. `POST /api/payments/checkout/` — user picks a provider; `PaymentService`
   asks the matching strategy to `initiate()` a payment and stores a
   `Payment` row with `status=pending`.
3. `POST /api/payments/{transaction_id}/confirm/` (client-driven) **or**
   the provider's webhook/callback (server-driven) — the provider
   confirms/fails the payment.
4. On success: `Order.status -> paid` and stock is reduced per line item.
   On failure: `Payment.status -> failed`, order stays `pending` so the
   user can retry with another provider.
