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


@router.callback_query(CatcherFactory.filter())
async def manage_catcher(
    query: CallbackQuery,
    callback_data: CatcherFactory,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    catcher_id = callback_data.id
    catcher = await session.get(Catcher, catcher_id)

    if catcher.is_connected:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_action_with_catcher(back_to="catchers"),
        )
    else:
        await query.message.edit_text(
            "Выберите действие",
            reply_markup=await ik_connect_catcher(back_to="catchers"),
        )
    await state.set_state(CatcherState.actions)
    await state.update_data(catcher_id=catcher_id)


@router.callback_query(CatcherState.actions, F.data == "connect_catcher")
async def connect_catcher(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    catcher_id: int | None = (await state.get_data()).get("catcher_id")

    if not catcher_id:
        await query.message.answer(text="Ошибка: catcher_id пустой в state")
        return

    catcher = await session.get(Catcher, catcher_id)

    if not catcher:
        await query.message.answer(text="Ошибка: catcher не найден в базе данных")
        return

    asyncio.create_task(
        fn.Manager.start_bot(
            catcher.phone,
            catcher.path_session,
            catcher.api_id,
            catcher.api_hash,
        )
    )
    await query.message.edit_text("Пытаемся подключить Ловца с уже существующей сессией...")
    await asyncio.sleep(2)
    if await fn.Manager.bot_run(catcher.phone):
        catcher.is_connected = True
        await session.commit()
        await query.message.edit_text(
            "Ловец успешно подключен!",
            reply_markup=await ik_action_with_catcher(back_to="catchers"),
        )
        return

    result = await fn.Telethon.send_code_via_telethon(
        catcher.phone,
        catcher.api_id,
        catcher.api_hash,
        catcher.path_session,
    )
    if result.success:
        await query.message.edit_text(
            "К сожалению, Ловец не смог подключиться по старой сессии, поэтому мы отправили код, \
            как получите его отправьте мне"
        )
    else:
        await query.message.answer(f"Ошибка при отправке кода: {result.message}")
        return

    await state.update_data(
        api_id=catcher.api_id,
        api_hash=catcher.api_hash,
        phone=catcher.phone,
        phone_code_hash=result.message,
        path_session=catcher.path_session,
        save_catcher=False,
    )
    await state.set_state(UserAdminState.enter_code)


@router.callback_query(CatcherState.actions, F.data == "disconnect_catcher")
async def disconnected_catcher(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    catcher_id: int | None = (await state.get_data()).get("catcher_id")

    if not catcher_id:
        await query.message.answer(text="Ошибка: catcher_id пустой в state")
        return

    catcher = await session.get(Catcher, catcher_id)

    if not catcher:
        await query.message.answer(text="Ошибка: catcher не найден в базе данных")
        return

    catcher.is_connected = False
    await session.commit()

    await fn.Manager.stop_bot(phone=catcher.phone)

    await fn.state_clear(state)
    await query.message.edit_text("Ловец отключен", reply_markup=await ik_admin_panel())


@router.callback_query(CatcherState.actions, F.data == "delete_catcher")
async def delete_catcher(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    catcher_id: int | None = (await state.get_data()).get("catcher_id")

    if not catcher_id:
        await query.message.answer(text="Ошибка: catcher_id пустой в state")
        return

    catcher = await session.get(Catcher, catcher_id)

    if not catcher:
        await query.message.answer(text="Ошибка: catcher не найден в базе данных")
        return

    await fn.Manager.stop_bot(phone=catcher.phone, delete_session=True)

    await session.delete(catcher)
    await session.commit()

    await fn.state_clear(state)
    await query.message.edit_text("Бот удален", reply_markup=await ik_admin_panel())


@router.callback_query(CatcherState.actions, BackFactory.filter(F.to == "catchers"))
async def back(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await fn.state_clear(state)
    catchers = (await session.scalars(select(Catcher))).all()
    await query.message.edit_text(
        "Ловцы",
        reply_markup=await ik_available_catchers(list(catchers)),
    )
