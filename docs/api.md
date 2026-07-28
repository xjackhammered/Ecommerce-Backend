# API Documentation

Interactive, always-up-to-date docs are auto-generated from the code via
**drf-spectacular**:

- OpenAPI schema (JSON): `GET /api/schema/`
- Swagger UI: `GET /api/docs/`

You can also import the schema into Postman: Postman → Import → paste the
`/api/schema/` URL.

## Endpoint reference

### Auth / Users
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/users/register/` | Public | Register a new user |
| POST | `/api/users/login/` | Public | Obtain JWT access + refresh tokens |
| POST | `/api/users/login/refresh/` | Public | Refresh an access token |
| GET | `/api/users/me/` | JWT | Current user's profile |
| GET | `/api/users/me/orders/` | JWT | Current user's own orders |
| GET | `/api/users/me/payments/` | JWT | Current user's own payments |

### Products & Categories
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/products/` | JWT | List active products (admins see all) |
| POST | `/api/products/` | Admin | Create a product |
| GET | `/api/products/{id}/` | JWT | Product detail |
| PATCH/PUT | `/api/products/{id}/` | Admin | Update a product |
| DELETE | `/api/products/{id}/` | Admin | Delete a product |
| GET | `/api/categories/` | JWT | List categories |
| POST | `/api/categories/` | Admin | Create a category |
| GET | `/api/categories/tree/` | JWT | Full category tree (DFS-built, Redis-cached) |
| GET | `/api/categories/{id}/recommended-products/` | JWT | Active products across a category's sub-tree |

### Orders
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/orders/` | JWT | Create an order: `{"items": [{"product_id": 1, "quantity": 2}]}` |
| GET | `/api/orders/` | JWT | List the caller's own orders |
| GET | `/api/orders/{id}/` | JWT | Retrieve one of the caller's own orders |

### Payments
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/payments/checkout/` | JWT | `{"order_id": 1, "provider": "stripe"|"bkash"}` -> initiates payment |
| POST | `/api/payments/{transaction_id}/confirm/` | JWT | Confirms/executes the payment with the provider |
| POST | `/api/payments/stripe/webhook/` | Stripe signature | Stripe server-to-server webhook |
| GET | `/api/payments/bkash/callback/` | Public redirect | bKash browser redirect after approval/cancellation |

## Example: full checkout flow

```bash
# 1. Register + log in
curl -X POST localhost:8000/api/users/register/ -d '{"email":"a@b.com","password":"Passw0rd!"}' -H 'Content-Type: application/json'
curl -X POST localhost:8000/api/users/login/ -d '{"email":"a@b.com","password":"Passw0rd!"}' -H 'Content-Type: application/json'
# -> {"access": "...", "refresh": "..."}

# 2. Create an order
curl -X POST localhost:8000/api/orders/ \
  -H "Authorization: Bearer <access>" -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":1,"quantity":2}]}'

# 3. Checkout with Stripe
curl -X POST localhost:8000/api/payments/checkout/ \
  -H "Authorization: Bearer <access>" -H 'Content-Type: application/json' \
  -d '{"order_id":1,"provider":"stripe"}'

# 4. Confirm (test mode)
curl -X POST localhost:8000/api/payments/<transaction_id>/confirm/ \
  -H "Authorization: Bearer <access>" -H 'Content-Type: application/json' \
  -d '{"payment_method":"pm_card_visa"}'
```
