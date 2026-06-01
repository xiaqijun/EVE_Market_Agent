from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.sde import SdeCategory, SdeItem, SdeRegion, SdeStation, SdeItemGroup


async def search_items(db: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    result = await db.execute(
        select(SdeItem).where(
            SdeItem.name.ilike(f"%{query}%"), SdeItem.is_published == True  # noqa: E712
        ).limit(limit)
    )
    items = result.scalars().all()
    return [{"type_id": i.type_id, "name": i.name, "group_id": i.group_id,
             "volume": i.volume, "base_price": i.base_price} for i in items]


async def get_item(db: AsyncSession, type_id: int) -> dict | None:
    result = await db.execute(select(SdeItem).where(SdeItem.type_id == type_id))
    item = result.scalar_one_or_none()
    if not item:
        return None
    return {"type_id": item.type_id, "name": item.name, "group_id": item.group_id,
            "volume": item.volume, "base_price": item.base_price}


async def get_item_sde_context(db: AsyncSession, type_id: int) -> str:
    item = await get_item(db, type_id)
    if not item:
        return ""
    result = await db.execute(
        select(SdeItemGroup).where(SdeItemGroup.group_id == item["group_id"])
    )
    group = result.scalar_one_or_none()
    group_name = group.name if group else "未知"
    return (
        f"物品名称: {item['name']}\n"
        f"物品分组: {group_name}\n"
        f"体积: {item['volume']} m³\n"
        f"基础价格: {item['base_price']:,.2f} ISK\n"
    )


async def get_all_regions(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SdeRegion))
    return [{"region_id": r.region_id, "name": r.name} for r in result.scalars().all()]


async def get_item_groups(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SdeItemGroup))
    return [{"group_id": g.group_id, "name": g.name, "category_id": g.category_id}
            for g in result.scalars().all()]


async def search_stations(db: AsyncSession, query: str, limit: int = 10) -> list[dict]:
    result = await db.execute(
        select(SdeStation).where(SdeStation.name.ilike(f"%{query}%")).limit(limit)
    )
    return [{"station_id": s.station_id, "name": s.name, "system_id": s.system_id}
            for s in result.scalars().all()]


async def get_all_categories(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(SdeCategory))
    return [{"category_id": c.category_id, "name": c.name} for c in result.scalars().all()]
