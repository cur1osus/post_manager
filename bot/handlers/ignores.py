from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import select

from bot.db.models import Ignore, UserDB
from bot.keyboards.factories import (
    ArrowInfoFactory,
    BackFactory,
    CancelFactory,
    DeleteInfoFactory,
    InfoFactory,
)
from bot.keyboards.inline import (
    ik_add_or_delete,
    ik_cancel_action,
    ik_num_matrix,
    ik_profile,
)
from bot.states import InfoIgnoresState, UserState
from bot.utils import fn
from bot.utils.func import Chunker

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = Router()
logger = logging.getLogger(__name__)

IF_NONE_RESULT = "Нет игноров"


async def pretty_ignores(
    ignores: list[Ignore],
    start_numerate: int,
    sep: str = "\n",
) -> str | None:
    if not ignores:
        return None
    s = sep.join(
        f"{ind + 1}) {ignore.content}"
        for ind, ignore in enumerate(ignores, start=start_numerate)
    )
    return s[: fn.max_length_message] + "..." if len(s) > fn.max_length_message else s


@router.callback_query(UserState.actions, InfoFactory.filter(F.key == "ignore"))
async def info_ignores(
    query: CallbackQuery | Message,
    state: FSMContext,
    session: AsyncSession,
    user: UserDB,
) -> None:
    fetched_data = user.ignores
    ch = Chunker()
    text = await ch(
        model_db=None,
        session=session,
        ind_chunk=None,
        func_to_str=pretty_ignores,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )

    await query.message.edit_text(
        text=text,
        reply_markup=await ik_add_or_delete(
            ch.ind_chunk,
            ch.quantity_chunks,
        ),
    )

    await state.set_state(InfoIgnoresState.info)
    await state.update_data(
        ind_chunk=ch.ind_chunk,
        quantity_chunks=ch.quantity_chunks,
    )


@router.callback_query(InfoIgnoresState.info, ArrowInfoFactory.filter())
async def arrow_ignores_info(
    query: CallbackQuery,
    callback_data: ArrowInfoFactory,
    state: FSMContext,
    user: UserDB,
    session: AsyncSession,
) -> None:
    arrow = callback_data.to

    data_state = await state.get_data()
    ind_chunk = data_state["ind_chunk"]
    quantity_chunks = data_state["quantity_chunks"]

    match arrow:
        case "left":
            ind_chunk = ind_chunk - 1 if ind_chunk > 1 else quantity_chunks
        case "right":
            ind_chunk = ind_chunk + 1 if ind_chunk < quantity_chunks else 1

    fetched_data = user.ignores
    ch = Chunker()
    text = await ch(
        model_db=None,
        session=session,
        ind_chunk=ind_chunk,
        func_to_str=pretty_ignores,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
        )
    except Exception:
        await query.answer("-")

    await state.update_data(ind_chunk=ch.ind_chunk, quantity_chunks=ch.quantity_chunks)


@router.callback_query(InfoIgnoresState.info, F.data == "add")
async def add_ignores(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await query.message.edit_text(
        "Введите игнор слово или предложение:",
        reply_markup=await ik_cancel_action(),
    )
    await state.set_state(InfoIgnoresState.add)


@router.message(InfoIgnoresState.add)
async def ignores_ids_to_add(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    user: UserDB,
) -> None:
    ignores_to_add = [username.strip() for username in message.text.splitlines()]

    data_state = await state.get_data()

    ignores = await user.awaitable_attrs.ignores
    ignores_contents = [ignore.content for ignore in ignores]
    new_ignores = [
        Ignore(content=ignore)
        for ignore in ignores_to_add
        if ignore not in ignores_contents
    ]

    user.ignores.extend(new_ignores)
    await session.commit()

    async with sessionmaker() as new_session:
        fetched_data = (
            await new_session.scalars(select(Ignore).where(Ignore.user_id == user.id))
        ).all()
        ch = Chunker()
        text = await ch(
            model_db=None,
            session=new_session,
            ind_chunk=data_state["ind_chunk"],
            func_to_str=pretty_ignores,
            if_none_result=IF_NONE_RESULT,
            fetched_data=list(fetched_data),
        )

    msg = await message.answer(
        text=text,
        reply_markup=await ik_add_or_delete(
            ch.ind_chunk,
            ch.quantity_chunks,
        ),
    )
    await state.update_data(
        ind_chunk=ch.ind_chunk,
        quantity_chunks=ch.quantity_chunks,
    )
    await fn.set_general_message(state, msg)
    await state.set_state(InfoIgnoresState.info)


@router.callback_query(InfoIgnoresState.info, F.data == "delete")
async def delete_ignores(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserDB,
) -> None:
    data_state = await state.get_data()

    fetched_data = user.ignores
    ch = Chunker()
    await ch(
        model_db=None,
        session=session,
        ind_chunk=data_state["ind_chunk"],
        func_to_str=pretty_ignores,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )

    ignores_ids = [ignore.id for ignore in ch.chunk]
    start_ind = (ch.ind_chunk - 1) * 10
    await query.message.edit_reply_markup(
        reply_markup=await ik_num_matrix(ignores_ids, start_ind, "info")
    )
    await state.set_state(InfoIgnoresState.delete)
    await state.update_data(ignores_ids=ignores_ids)


@router.callback_query(InfoIgnoresState.delete, DeleteInfoFactory.filter())
async def ignores_delete_by_id_obj(
    query: CallbackQuery,
    callback_data: DeleteInfoFactory,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    user: UserDB,
) -> None:
    ignore_id_to_delete = callback_data.id
    ignore = await session.get(Ignore, ignore_id_to_delete)

    await session.delete(ignore)
    await session.commit()

    async with sessionmaker() as new_session:
        data_state = await state.get_data()
        fetched_data = (
            await new_session.scalars(select(Ignore).where(Ignore.user_id == user.id))
        ).all()
        ch = Chunker()
        text = await ch(
            model_db=None,
            session=new_session,
            ind_chunk=data_state["ind_chunk"],
            func_to_str=pretty_ignores,
            if_none_result=IF_NONE_RESULT,
            fetched_data=list(fetched_data),
        )
    ignores_ids = [ignore.id for ignore in ch.chunk]
    start_ind = (ch.ind_chunk - 1) * 10

    await query.message.edit_text(
        text,
        reply_markup=await ik_num_matrix(ignores_ids, start_ind, "info"),
    )
    await state.update_data(ignores_ids=ignores_ids)


@router.callback_query(InfoIgnoresState.delete, BackFactory.filter(F.to == "info"))
async def back_info(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserDB,
) -> None:
    await info_ignores(query, state, session, user)


@router.callback_query(InfoIgnoresState.info, BackFactory.filter(F.to == "default"))
async def back_ignores(
    query: CallbackQuery,
    state: FSMContext,
    user: UserDB,
    sub_active: bool,
) -> None:
    data = await state.get_data()

    await fn.state_clear(state)
    await state.set_data(data)

    await state.set_state(UserState.actions)

    text = await fn.return_profile_text(user)
    keyboard = await fn.return_profile_keyboard(sub_active)

    await query.message.edit_text(text=text, reply_markup=await keyboard())


@router.callback_query(InfoIgnoresState.add, CancelFactory.filter(F.to == "default"))
async def cancel_add_ignores(
    query: CallbackQuery, state: FSMContext, session: AsyncSession, user: UserDB
) -> None:
    data_state = await state.get_data()

    fetched_data = user.ignores
    ch = Chunker()
    text = await ch(
        model_db=None,
        session=session,
        ind_chunk=data_state["ind_chunk"],
        func_to_str=pretty_ignores,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )

    msg = await query.message.answer(
        text=text,
        reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
    )

    await fn.set_general_message(state, msg)
    await state.set_state(InfoIgnoresState.info)
