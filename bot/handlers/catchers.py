from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import select

from bot.db.models import Catcher
from bot.keyboards.inline import (
    ik_available_catchers,
    ik_back,
)
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "catchers")
async def show_bots(
    query: CallbackQuery,
    session: AsyncSession,
) -> None:
    catchers = (await session.scalars(select(Catcher))).all()
    if not catchers:
        await query.message.edit_text(
            text="Ловцов еще нет", reply_markup=await ik_back()
        )
        return
    for catcher in catchers:
        catcher.is_connected = await fn.Manager.bot_run(catcher.phone)
    await session.commit()
    await query.message.edit_text(
        "Ловцы",
        reply_markup=await ik_available_catchers(list(catchers)),
    )
