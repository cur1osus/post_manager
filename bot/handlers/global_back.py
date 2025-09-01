from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router

from bot.keyboards.factories import BackFactory
from bot.keyboards.inline import ik_admin_panel
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from aiogram.fsm.context import FSMContext
    from bot.db.models import UserDB

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(BackFactory.filter(F.to == "default"))
async def back_default(query: CallbackQuery, state: FSMContext, user: UserDB) -> None:
    await fn.state_clear(state)
    if user.is_admin:
        await query.message.edit_text(
            "Привет, админ!",
            reply_markup=await ik_admin_panel(),
        )
    else:
        await query.message.edit_text("Привет, дружище!")
