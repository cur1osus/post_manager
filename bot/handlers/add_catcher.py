from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.fsm.state import any_state
from aiogram.types.reply_keyboard_remove import ReplyKeyboardRemove
from sqlalchemy import select
from telethon.tl.functions.upload import os

from bot.db.models import Catcher, UserDB
from bot.keyboards.inline import ik_admin_panel
from bot.keyboards.reply import rk_cancel
from bot.settings import se
from bot.states import UserAdminState
from bot.utils import fn

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router()
logger = logging.getLogger(__name__)

background_tasks = set()


@router.message(any_state, F.text == "Отмена")
async def cancel_add(
    message: Message,
    state: FSMContext,
) -> None:
    await fn.state_clear(state)
    await message.answer(
        "Добавление Ловца отменено",
        reply_markup=ReplyKeyboardRemove(),
    )
    msg = await message.answer("Привет, админ!", reply_markup=await ik_admin_panel())
    await fn.set_general_message(state, msg)


@router.callback_query(F.data == "add_new_catcher")
async def add_new_catcher(
    query: CallbackQuery,
    state: FSMContext,
    user: UserDB,
) -> None:
    if not user.is_admin:
        await query.message.answer("Вы не администратор")
        return
    await query.message.delete()
    await query.message.answer("Введите api_id", reply_markup=await rk_cancel())
    await state.set_state(UserAdminState.enter_api_id)


@router.message(UserAdminState.enter_api_id)
async def enter_api_id(message: Message, state: FSMContext) -> None:
    await state.update_data(api_id=message.text)
    await message.answer("Введите api_hash", reply_markup=None)
    await state.set_state(UserAdminState.enter_api_hash)


@router.message(UserAdminState.enter_api_hash)
async def enter_api_hash(message: Message, state: FSMContext) -> None:
    await state.update_data(api_hash=message.text)
    await message.answer("Введите phone", reply_markup=None)
    await state.set_state(UserAdminState.enter_phone)


@router.message(UserAdminState.enter_phone)
async def enter_phone(message: Message, state: FSMContext) -> None:
    if not message.text:
        return

    os.makedirs(se.path_to_folder, exist_ok=True)

    await state.update_data(phone=message.text)

    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")

    if not api_id or not api_hash:
        await message.answer(
            "Произошла ошибка, не обнаружено API ID или API HASH, нажмите \
            'Отмена' и попробуйте снова"
        )
        return

    relative_path = f"{se.path_to_folder}/{message.text}"
    path_session = os.path.abspath(f"{relative_path}.session")

    result = await fn.Telethon.send_code_via_telethon(
        message.text,
        int(api_id),
        api_hash,
        path_session,
    )

    if not result.success:
        t = str(result.message)
        await message.answer(t, reply_markup=None)
        return

    phone_code_hash = result.message
    await state.update_data(
        phone_code_hash=phone_code_hash,
        path_session=path_session,
    )
    await message.answer("Введите code", reply_markup=None)
    await state.set_state(UserAdminState.enter_code)


@router.message(UserAdminState.enter_code)
async def enter_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    if not message.text:
        return

    data = await state.get_data()

    is_password = data.get("is_password", False)
    code = data.get("code") if is_password else message.text
    password = message.text if is_password else None

    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    phone_code_hash = data["phone_code_hash"]
    path_session = data["path_session"]

    r = await fn.Telethon.create_telethon_session(
        phone,
        code,  # pyright: ignore
        int(api_id),
        api_hash,
        phone_code_hash,
        password,
        path_session,
    )
    if r.message == "password_required":
        await message.answer("Введите пароль", reply_markup=None)
        await state.update_data(code=code, is_password=True)
        return
    if not r.success:
        t = str(r.message)
        await message.answer(t, reply_markup=None)
        return

    save_catcher = data.get("save_catcher", True)
    if save_catcher:
        catcher_exist = await session.scalar(
            select(Catcher).where(Catcher.api_hash == api_hash)
        )
        if catcher_exist:
            await message.answer(
                "Ловец уже зарегистрирован",
                reply_markup=ReplyKeyboardRemove(),
            )
            await fn.state_clear(state)
            return

        c = Catcher(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            path_session=path_session,
            is_connected=True,
        )
        session.add(c)
        await session.commit()

    _task = asyncio.create_task(
        fn.Manager.start_bot(phone, path_session, api_id, api_hash)
    )
    background_tasks.add(_task)
    _task.add_done_callback(background_tasks.discard)

    await fn.state_clear(state)

    await message.answer("Ловец начал работу", reply_markup=ReplyKeyboardRemove())
