# app/auth.py
from fastapi import Depends, Header, HTTPException, status
import sqlalchemy as sa
from app.db import get_db


def withApiAuth(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db=Depends(get_db),
) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    cid = db.execute(
        sa.text(
            """
            SELECT customer_id
              FROM api_keys
             WHERE token_hash = encode(digest(:tok, 'sha256'), 'hex')
             LIMIT 1
        """
        ),
        {"tok": x_api_key},
    ).scalar_one_or_none()

    if not cid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return str(cid)
