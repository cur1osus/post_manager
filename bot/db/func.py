from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import UserDB


async def _get_user_db_model(session: AsyncSession, user_id: int) -> UserDB | None:
    return await session.scalar(select(UserDB).where(UserDB.user_id == user_id))
