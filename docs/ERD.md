# Entity-Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    ORDERS ||--o{ ORDER_ITEMS : contains
    ORDERS ||--o{ PAYMENTS : "paid via"
    PRODUCTS ||--o{ ORDER_ITEMS : "ordered as"
    CATEGORIES ||--o{ PRODUCTS : classifies
    CATEGORIES ||--o{ CATEGORIES : "parent of"

    USERS {
        bigint id PK
        string email UK
        string full_name
        bool is_admin
        bool is_active
        datetime created_at
        datetime updated_at
    }

    CATEGORIES {
        bigint id PK
        string name
        bigint parent_id FK
        datetime created_at
    }

    PRODUCTS {
        bigint id PK
        string name
        string sku UK
        text description
        decimal price
        int stock
        string status
        bigint category_id FK
        datetime created_at
        datetime updated_at
    }

    ORDERS {
        bigint id PK
        bigint user_id FK
        decimal total_amount
        string status
        datetime created_at
        datetime updated_at
    }

    ORDER_ITEMS {
        bigint id PK
        bigint order_id FK
        bigint product_id FK
        int quantity
        decimal price
        decimal subtotal
    }

    PAYMENTS {
        bigint id PK
        bigint order_id FK
        string provider
        string transaction_id UK
        string status
        json raw_response
        datetime created_at
        datetime updated_at
    }
```

## Notes

- `products.sku` and `payments.transaction_id` are unique and indexed for fast lookups.
- `orders.status` moves `pending -> paid` or `pending -> canceled`; a `paid`
  order cannot be canceled directly (enforced in `OrderService.cancel`).
- `order_items.price` / `subtotal` are **snapshots** taken at order-creation
  time, so a later change to `products.price` never rewrites historical
  orders.
- `categories.parent_id` is self-referencing, forming the tree that
  `CategoryTreeService` walks with DFS and caches in Redis.
- Indexes exist on all foreign keys plus `products.sku`, `products.status`,
  `orders.status`, `payments.provider`, `payments.status` to keep the
  common list/filter queries fast as data grows.
