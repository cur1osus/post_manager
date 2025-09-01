from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from bot.db.models import Catcher
from bot.keyboards.factories import BackFactory, CatcherFactory
from bot.keyboards.inline import (
    ik_action_with_catcher,
    ik_admin_panel,
    ik_available_catchers,
    ik_connect_catcher,
)
from bot.states import CatcherState, UserAdminState
from bot.utils import fn
from sqlalchemy import select

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "renew_sub")
async def renew_subscription(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await query.answer("Функция еще не реализована!", show_alert=True)
