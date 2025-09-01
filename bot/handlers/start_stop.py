from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router

from bot.db.models import UserDB
from bot.states import UserState
from bot.utils import fn
from aiogram.exceptions import TelegramBadRequest

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(UserState.actions, F.data == "start_send_notify")
async def start_send_notification(
    query: CallbackQuery,
    session: AsyncSession,
    user: UserDB,
    sub_active: bool,
) -> None:
    user.receive_notifications = True
    await session.commit()

    text = await fn.return_profile_text(user)
    keyboard = await fn.return_profile_keyboard(sub_active)
    try:
        await query.message.edit_text(text=text, reply_markup=await keyboard())
    except TelegramBadRequest:
        await query.answer(
            text="Статус уже установлен!",
            show_alert=True,
        )


@router.callback_query(UserState.actions, F.data == "stop_send_notify")
async def stop_send_notification(
    query: CallbackQuery,
    session: AsyncSession,
    user: UserDB,
    sub_active: bool,
) -> None:
    user.receive_notifications = False
    await session.commit()

    text = await fn.return_profile_text(user)
    keyboard = await fn.return_profile_keyboard(sub_active)
    try:
        await query.message.edit_text(text=text, reply_markup=await keyboard())
    except TelegramBadRequest:
        await query.answer(
            text="Статус уже установлен!",
            show_alert=True,
        )
