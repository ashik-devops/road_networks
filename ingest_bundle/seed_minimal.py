# Seed only: insert a customer and a hashed API key.


import os, argparse
import sqlalchemy as sa
from sqlalchemy import text

DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
)


def ensure_customer(conn, name):
    row = conn.execute(
        text(
            """
        INSERT INTO customers(name)
        VALUES (:name)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
    """
        ),
        {"name": name},
    ).one()
    return row[0]


def ensure_api_key(conn, customer_id, token):
    # store only the hash of the API key
    conn.execute(
        text(
            """
        INSERT INTO api_keys(customer_id, token_hash)
        VALUES (:cid, encode(digest(:tok, 'sha256'), 'hex'))
        ON CONFLICT (token_hash) DO NOTHING
    """
        ),
        {"cid": customer_id, "tok": token},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB_URL)
    ap.add_argument("--customer", default="Acme Corp")
    ap.add_argument("--api-key", default="dev-123")
    args = ap.parse_args()

    engine = sa.create_engine(args.db, future=True)
    with engine.begin() as conn:
        cust_id = ensure_customer(conn, args.customer)
        ensure_api_key(conn, cust_id, args.api_key)
        print(f"Seeded customer '{args.customer}' with API key (hashed).")


if __name__ == "__main__":
    main()
