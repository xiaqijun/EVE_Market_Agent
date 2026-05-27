"""Sync EVE character market transactions from ESI into user_trades."""
import asyncio
from datetime import datetime, timezone
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.tasks.celery_app import celery_app
from app.database import async_session, engine
from app.models.eve_character import EveCharacter
from app.models.trade import UserTrade
from app.services.encryption import decrypt_token
from app.config import settings


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def sync_character_trades(self, character_id: int | None = None):
    asyncio.get_event_loop().run_until_complete(engine.dispose())
    return asyncio.get_event_loop().run_until_complete(_async_sync(character_id))


async def _async_sync(character_id: int | None):
    async with async_session() as db:
        if character_id:
            result = await db.execute(
                select(EveCharacter).where(EveCharacter.character_id == character_id)
            )
        else:
            result = await db.execute(select(EveCharacter))
        characters = result.scalars().all()

        for char in characters:
            try:
                token = await _refresh_if_needed(db, char)
                if not token:
                    continue

                orders = await _get_character_orders(char.character_id, token)
                wallet = await _get_wallet_transactions(char.character_id, token)

                for order in orders:
                    await _upsert_order_as_trade(db, char, order)

                for tx in wallet:
                    await _upsert_transaction(db, char, tx)

                await db.commit()
                print(f"[TRADE] Synced {char.character_name}: {len(orders)} orders, {len(wallet)} transactions")
            except Exception as e:
                print(f"[TRADE] Error syncing {char.character_name}: {type(e).__name__}: {e}")

        await db.commit()


async def _refresh_if_needed(db: AsyncSession, char: EveCharacter) -> str | None:
    from app.tasks.asset_sync import _refresh_if_needed
    return await _refresh_if_needed(db, char)


async def _get_character_orders(character_id: int, access_token: str) -> list:
    """Fetch character's market orders from ESI."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://esi.evetech.net/latest/characters/{character_id}/orders/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"[TRADE] Orders fetch failed: {resp.status_code}")
    except Exception as e:
        print(f"[TRADE] Orders fetch error: {e}")
    return []


async def _get_wallet_transactions(character_id: int, access_token: str) -> list:
    """Fetch character wallet transactions from ESI."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://esi.evetech.net/latest/characters/{character_id}/wallet/transactions/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code == 200:
                return resp.json()
            print(f"[TRADE] Wallet transactions fetch failed: {resp.status_code}")
    except Exception as e:
        print(f"[TRADE] Wallet transactions error: {e}")
    return []


async def _upsert_order_as_trade(db: AsyncSession, char: EveCharacter, order: dict):
    """Convert a market order into a user trade record if it's filled."""
    if order.get("state") != "expired" and order.get("volume_remain", 1) > 0:
        return

    existing = await db.execute(
        select(UserTrade).where(UserTrade.esi_order_id == order.get("order_id"))
    )
    if existing.scalar_one_or_none():
        return

    db.add(UserTrade(
        user_id=char.user_id,
        character_id=char.id,
        type_id=order.get("type_id", 0),
        station_id=order.get("location_id", 0),
        is_buy=order.get("is_buy_order", False),
        quantity=order.get("volume_total", 0) - order.get("volume_remain", 0),
        unit_price=order.get("price", 0),
        total_cost=(order.get("volume_total", 0) - order.get("volume_remain", 0)) * order.get("price", 0),
        broker_fee=0,
        tax=0,
        executed_at=datetime.fromisoformat(order["issued"].replace("Z", "+00:00")) if order.get("issued") else datetime.now(timezone.utc),
        esi_order_id=order.get("order_id"),
    ))


async def _upsert_transaction(db: AsyncSession, char: EveCharacter, tx: dict):
    """Convert a wallet transaction into a user trade record."""
    tx_id = tx.get("transaction_id")
    if not tx_id:
        return

    existing = await db.execute(
        select(UserTrade).where(UserTrade.esi_transaction_id == tx_id)
    )
    if existing.scalar_one_or_none():
        return

    db.add(UserTrade(
        user_id=char.user_id,
        character_id=char.id,
        type_id=tx.get("type_id", 0),
        station_id=tx.get("location_id", 0),
        is_buy=tx.get("is_buy", False),
        quantity=tx.get("quantity", 0),
        unit_price=tx.get("unit_price", 0),
        total_cost=tx.get("quantity", 0) * tx.get("unit_price", 0),
        broker_fee=0,
        tax=0,
        executed_at=datetime.fromisoformat(tx["date"].replace("Z", "+00:00")) if tx.get("date") else datetime.now(timezone.utc),
        esi_transaction_id=tx_id,
    ))
