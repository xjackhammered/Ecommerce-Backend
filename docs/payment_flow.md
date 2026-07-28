# Payment Flow Diagrams

## Stripe

```mermaid
sequenceDiagram
    participant U as User (Frontend)
    participant API as Backend API
    participant S as StripeStrategy
    participant Stripe as Stripe

    U->>API: POST /api/payments/checkout/ {order_id, provider: "stripe"}
    API->>S: initiate(order, amount)
    S->>Stripe: PaymentIntent.create(amount, currency)
    Stripe-->>S: payment_intent (id, client_secret, status=requires_payment_method)
    S-->>API: {transaction_id, status: pending, client_payload: {client_secret}}
    API-->>U: 201 {payment, client_secret}

    U->>API: POST /api/payments/{transaction_id}/confirm/ {payment_method}
    API->>S: confirm(transaction_id, payload)
    S->>Stripe: PaymentIntent.confirm(id, payment_method)
    Stripe-->>S: payment_intent (status=succeeded|canceled)
    S-->>API: {status: success|failed}
    API->>API: reduce stock (on success) + mark order paid
    API-->>U: 200 {payment: success|failed}

    Note over Stripe,API: In parallel, Stripe also fires a webhook
    Stripe--)API: POST /api/payments/stripe/webhook/ (payment_intent.succeeded)
    API->>API: verify signature -> handle_webhook_event() (idempotent)
```

## bKash (Tokenized Checkout, sandbox)

```mermaid
sequenceDiagram
    participant U as User (Frontend)
    participant API as Backend API
    participant B as BkashStrategy
    participant Bkash as bKash Sandbox

    U->>API: POST /api/payments/checkout/ {order_id, provider: "bkash"}
    API->>B: initiate(order, amount)
    B->>Bkash: POST /token/grant (app_key, app_secret, username, password)
    Bkash-->>B: id_token (cached in Redis until near-expiry)
    B->>Bkash: POST /checkout/create {amount, currency: BDT, callbackURL}
    Bkash-->>B: {paymentID, bkashURL}
    B-->>API: {transaction_id: paymentID, status: pending, client_payload: {bkash_url}}
    API-->>U: 201 {payment, bkash_url}

    U->>Bkash: Redirected to bkash_url, approves payment in bKash app/page
    Bkash--)API: GET /api/payments/bkash/callback/?paymentID=...&status=success
    API->>API: handle_webhook_event("bkash", paymentID, status)
    API->>API: reduce stock (on success) + mark order paid
    API-->>U: Redirect back to frontend order confirmation page

    Note over U,API: The client can also poll explicitly
    U->>API: POST /api/payments/{transaction_id}/confirm/
    API->>B: confirm(transaction_id, {})
    B->>Bkash: POST /checkout/execute {paymentID}
    Bkash-->>B: {transactionStatus: Completed|Failed}
    B-->>API: {status: success|failed}
```

## Shared failure/retry behavior

- A `failed` payment never touches stock or the order's status - the order
  stays `pending`, so the user can retry checkout with a different
  provider (`POST /api/payments/checkout/` again with `provider` switched).
- Both webhook/callback and the client-driven `confirm` endpoint route
  through the same `PaymentService` methods, so stock is only ever reduced
  once per order regardless of which path resolves the payment first
  (`Order.status != paid` is checked before reducing stock in the webhook
  path).
