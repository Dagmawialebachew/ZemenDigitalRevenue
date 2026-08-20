from __future__ import annotations

from decimal import Decimal

from backend.db.pool import Database


class OrderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create_order(
        self,
        *,
        public_id: str,
        user_id: int,
        product_id: int,
        list_price: Decimal,
        amount_due: Decimal,
        customer_offer_id: int | None = None,
        referral_attribution_id: int | None = None,
    ) -> int:
        discount_amount = max(Decimal("0"), list_price - amount_due)
        commissionable = discount_amount == 0
        sql = """
        INSERT INTO orders (
            public_id, user_id, product_id, list_price, amount_due,
            discount_amount, customer_offer_id, referral_attribution_id,
            commissionable
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        RETURNING id
        """
        async with self.db.acquire() as conn:
            value = await conn.fetchval(
                sql,
                public_id,
                user_id,
                product_id,
                list_price,
                amount_due,
                discount_amount,
                customer_offer_id,
                referral_attribution_id,
                commissionable,
            )
        return int(value)

    async def get_by_public_id(self, public_id: str):
        async with self.db.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM orders WHERE public_id=$1", public_id)
