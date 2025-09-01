from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import CommandObject, CommandStart

from bot.db.models import UserDB
from bot.keyboards.inline import ik_admin_panel, ik_user_panel
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import Message
    from sqlalchemy.ext.asyncio import AsyncSession


router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart(deep_link=True))
async def start_cmd_with_deep_link(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
    user: UserDB | None,
) -> None:
    args = command.args.split() if command.args else []
    deep_link = args[0]
    if deep_link and user:
        await message.answer(f"Вы стали админом! {deep_link}")
        user.is_admin = True
        await session.commit()
    else:
        await message.answer(
            "Для того чтобы стать админом, для начала отправьте команду /start, чтобы зарегестрироваться, а потом зайдите по ссылке"
        )


@router.message(CommandStart(deep_link=False))
async def start_cmd(
    message: Message,
    user: UserDB | None,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not user and message.from_user:
        full_name = message.from_user.full_name
        username = message.from_user.username or "none"
        new_user = UserDB(
            name=full_name,
            username=username,
            user_id=message.from_user.id,
            quantity_days_sub=3,
        )
        user = new_user
        session.add(new_user)
        await session.commit()

    if user.is_admin:
        msg = await message.answer(
            "Привет, админ!",
            reply_markup=await ik_admin_panel(),
        )
    else:
        msg = await message.answer(
            "Привет, дружище!",
            reply_markup=await ik_user_panel(),
        )

    await fn.set_general_message(state, msg)


# @router.message(Command(commands=["test"]))
# async def test(message: Message, state: FSMContext, user: UserDB) -> None:
#     await message.answer(
#         "Test command executed!", reply_markup=await ik_action_with_catcher()
#     )
#     await state.set_state(CatcherState.actions)
