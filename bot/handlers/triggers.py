from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import select

from bot.db.models import Trigger, UserDB
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
)
from bot.states import InfoTriggersState, UserState
from bot.utils import fn
from bot.utils.func import Chunker


if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = Router()
logger = logging.getLogger(__name__)

IF_NONE_RESULT = "Нет триггеров"
KEY = "trigger"


async def pretty_triggers(
    triggers: list[Trigger],
    start_numerate: int,
    sep: str = "\n",
) -> str | None:
    if not triggers:
        return None
    s = sep.join(
        f"{ind + 1}) {trigger.content}"
        for ind, trigger in enumerate(triggers, start=start_numerate)
    )
    return s[: fn.max_length_message] + "..." if len(s) > fn.max_length_message else s


@router.callback_query(UserState.actions, InfoFactory.filter(F.key == "trigger"))
async def info_triggers(
    query: CallbackQuery | Message,
    state: FSMContext,
    session: AsyncSession,
    user: UserDB,
) -> None:
    fetched_data = user.triggers
    ch = Chunker()
    text = await ch(
        model_db=None,
        session=session,
        ind_chunk=None,
        func_to_str=pretty_triggers,
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

    await state.set_state(InfoTriggersState.info)
    await state.update_data(
        ind_chunk=ch.ind_chunk,
        quantity_chunks=ch.quantity_chunks,
    )


@router.callback_query(InfoTriggersState.info, ArrowInfoFactory.filter())
async def arrow_triggers_info(
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

    fetched_data = user.triggers
    ch = Chunker()
    text = await ch(
        model_db=None,
        session=session,
        ind_chunk=ind_chunk,
        func_to_str=pretty_triggers,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
        )
    except Exception:
        await query.answer("Страница всего одна :(")

    await state.update_data(ind_chunk=ch.ind_chunk, quantity_chunks=ch.quantity_chunks)


@router.callback_query(InfoTriggersState.info, F.data == "add")
async def add_triggers(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await query.message.edit_text(
        "Введите триггер слово или предложение:",
        reply_markup=await ik_cancel_action(),
    )
    await state.set_state(InfoTriggersState.add)


@router.message(InfoTriggersState.add)
async def triggers_ids_to_add(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    user: UserDB,
) -> None:
    triggers_to_add = [username.strip() for username in message.text.splitlines()]

    data_state = await state.get_data()

    triggers = await user.awaitable_attrs.triggers
    triggers_contents = [trigger.content for trigger in triggers]
    new_triggers = [
        Trigger(content=trigger)
        for trigger in triggers_to_add
        if trigger not in triggers_contents
    ]

    user.triggers.extend(new_triggers)
    await session.commit()

    async with sessionmaker() as new_session:
        fetched_data = (
            await new_session.scalars(select(Trigger).where(Trigger.user_id == user.id))
        ).all()
        ch = Chunker()
        text = await ch(
            model_db=None,
            session=new_session,
            ind_chunk=data_state["ind_chunk"],
            func_to_str=pretty_triggers,
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
    await state.set_state(InfoTriggersState.info)


@router.callback_query(InfoTriggersState.info, F.data == "delete")
async def delete_triggers(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserDB,
) -> None:
    data_state = await state.get_data()

    fetched_data = user.triggers
    ch = Chunker()
    await ch(
        model_db=None,
        session=session,
        ind_chunk=data_state["ind_chunk"],
        func_to_str=pretty_triggers,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )

    triggers_ids = [trigger.id for trigger in ch.chunk]
    start_ind = (ch.ind_chunk - 1) * 10
    await query.message.edit_reply_markup(
        reply_markup=await ik_num_matrix(triggers_ids, start_ind, "info")
    )
    await state.set_state(InfoTriggersState.delete)
    await state.update_data(triggers_ids=triggers_ids)


@router.callback_query(InfoTriggersState.delete, DeleteInfoFactory.filter())
async def triggers_delete_by_id_obj(
    query: CallbackQuery,
    callback_data: DeleteInfoFactory,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    user: UserDB,
) -> None:
    trigger_id_to_delete = callback_data.id
    trigger = await session.get(Trigger, trigger_id_to_delete)

    await session.delete(trigger)
    await session.commit()

    async with sessionmaker() as new_session:
        data_state = await state.get_data()
        fetched_data = (
            await new_session.scalars(select(Trigger).where(Trigger.user_id == user.id))
        ).all()
        ch = Chunker()
        text = await ch(
            model_db=None,
            session=new_session,
            ind_chunk=data_state["ind_chunk"],
            func_to_str=pretty_triggers,
            if_none_result=IF_NONE_RESULT,
            fetched_data=list(fetched_data),
        )
    triggers_ids = [trigger.id for trigger in ch.chunk]
    start_ind = (ch.ind_chunk - 1) * 10

    await query.message.edit_text(
        text,
        reply_markup=await ik_num_matrix(triggers_ids, start_ind, "info"),
    )
    await state.update_data(triggers_ids=triggers_ids)


@router.callback_query(InfoTriggersState.delete, BackFactory.filter(F.to == "info"))
async def back_info(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: UserDB,
) -> None:
    await info_triggers(query, state, session, user)


@router.callback_query(InfoTriggersState.info, BackFactory.filter(F.to == "default"))
async def back_triggers(
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


@router.callback_query(InfoTriggersState.add, CancelFactory.filter(F.to == "default"))
async def cancel_add_triggers(
    query: CallbackQuery, state: FSMContext, session: AsyncSession, user: UserDB
) -> None:
    data_state = await state.get_data()

    fetched_data = user.triggers
    ch = Chunker()
    text = await ch(
        model_db=None,
        session=session,
        ind_chunk=data_state["ind_chunk"],
        func_to_str=pretty_triggers,
        if_none_result=IF_NONE_RESULT,
        fetched_data=fetched_data,
    )

    msg = await query.message.answer(
        text=text,
        reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
    )

    await fn.set_general_message(state, msg)
    await state.set_state(InfoTriggersState.info)
