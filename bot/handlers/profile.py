from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router

from bot.db.models import UserDB
from bot.states import UserState
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "profile")
async def user_profile(
    query: CallbackQuery, state: FSMContext, user: UserDB, sub_active: bool
) -> None:
    text = await fn.return_profile_text(user)
    keyboard = await fn.return_profile_keyboard(sub_active)
    await query.message.edit_text(text=text, reply_markup=await keyboard())
    await state.set_state(UserState.actions)
