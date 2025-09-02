from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import F, Router
from sqlalchemy import select

from bot.db.models import MonitoringChannel
from bot.keyboards.factories import (
    ArrowInfoFactory,
    BackFactory,
    CancelFactory,
    DeleteInfoFactory,
    InfoFactory,
)
from bot.keyboards.inline import (
    ik_action_with_catcher,
    ik_add_or_delete,
    ik_cancel_action,
    ik_num_matrix,
)
from bot.states import CatcherState, InfoChannelsState
from bot.utils import fn
from bot.utils.func import Chunker

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

router = Router()
logger = logging.getLogger(__name__)

IF_NONE_RESULT = "Нет каналов"


async def pretty_channels(
    channels: list[MonitoringChannel],
    start_numerate: int,
    sep: str = "\n",
) -> str | None:
    if not channels:
        return None
    s = sep.join(
        f"{ind + 1}) {channel.username} ({channel.title or '?'})"
        for ind, channel in enumerate(channels, start=start_numerate)
    )
    return s[: fn.max_length_message] + "..." if len(s) > fn.max_length_message else s


@router.callback_query(CatcherState.actions, InfoFactory.filter(F.key == "channels"))
async def info_channels(
    query: CallbackQuery | Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    ch = Chunker()
    text = await ch(
        model_db=MonitoringChannel,
        session=session,
        ind_chunk=None,
        func_to_str=pretty_channels,
        if_none_result=IF_NONE_RESULT,
    )

    await query.message.edit_text(
        text=text,
        reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
    )

    await state.set_state(InfoChannelsState.info)
    await state.update_data(
        ind_chunk=ch.ind_chunk,
        quantity_chunks=ch.quantity_chunks,
    )


@router.callback_query(InfoChannelsState.info, ArrowInfoFactory.filter())
async def arrow_channels_info(
    query: CallbackQuery,
    callback_data: ArrowInfoFactory,
    state: FSMContext,
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

    ch = Chunker()
    text = await ch(
        model_db=MonitoringChannel,
        session=session,
        ind_chunk=ind_chunk,
        func_to_str=pretty_channels,
        if_none_result=IF_NONE_RESULT,
    )
    try:
        await query.message.edit_text(
            text=text,
            reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
        )
    except Exception:
        await query.answer("Страница всего одна :(")

    await state.update_data(ind_chunk=ch.ind_chunk, quantity_chunks=ch.quantity_chunks)


@router.callback_query(InfoChannelsState.info, F.data == "add")
async def add_channels(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    await query.message.edit_text(
        "Введите id канал(-а, -ов)",
        reply_markup=await ik_cancel_action(),
    )
    await state.set_state(InfoChannelsState.add)


@router.message(InfoChannelsState.add)
async def channels_ids_to_add(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    usernames_to_add = []
    for username in message.text.splitlines():
        username = username.strip()
        if r := fn.Text.clean_invite_link(username):
            usernames_to_add.append(r)
        elif username.startswith("-"):
            usernames_to_add.append(username)
        elif not username.startswith("@"):
            usernames_to_add.append(f"@{username}")
        else:
            usernames_to_add.append(username)

    data_state = await state.get_data()

    channels = (await session.scalars(select(MonitoringChannel))).all()
    channels_usernames = [channel.username for channel in channels]
    new_channels = [
        MonitoringChannel(username=username)
        for username in usernames_to_add
        if username not in channels_usernames
    ]

    session.add_all(new_channels)
    await session.commit()

    async with sessionmaker() as new_session:
        ch = Chunker()
        text = await ch(
            model_db=MonitoringChannel,
            session=new_session,
            ind_chunk=data_state["ind_chunk"],
            func_to_str=pretty_channels,
            if_none_result=IF_NONE_RESULT,
        )

    msg = await message.answer(
        text=text,
        reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
    )
    await state.update_data(
        ind_chunk=ch.ind_chunk,
        quantity_chunks=ch.quantity_chunks,
    )
    await fn.set_general_message(state, msg)
    await state.set_state(InfoChannelsState.info)


@router.callback_query(InfoChannelsState.info, F.data == "delete")
async def delete_channels(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_state = await state.get_data()
    ch = Chunker()
    await ch(
        model_db=MonitoringChannel,
        session=session,
        ind_chunk=data_state["ind_chunk"],
        func_to_str=pretty_channels,
        if_none_result=IF_NONE_RESULT,
    )

    channels_ids = [channel.id for channel in ch.chunk]
    start_ind = (ch.ind_chunk - 1) * 10
    await query.message.edit_reply_markup(
        reply_markup=await ik_num_matrix(channels_ids, start_ind, "info")
    )
    await state.set_state(InfoChannelsState.delete)
    await state.update_data(channels_ids=channels_ids)


@router.callback_query(InfoChannelsState.delete, DeleteInfoFactory.filter())
async def channels_delete_by_id_obj(
    query: CallbackQuery,
    callback_data: DeleteInfoFactory,
    state: FSMContext,
    session: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    channel_id_to_delete = callback_data.id
    channel = await session.get(MonitoringChannel, channel_id_to_delete)

    await session.delete(channel)
    await session.commit()

    async with sessionmaker() as new_session:
        data_state = await state.get_data()
        ch = Chunker()
        text = await ch(
            model_db=MonitoringChannel,
            session=new_session,
            ind_chunk=data_state["ind_chunk"],
            func_to_str=pretty_channels,
            if_none_result=IF_NONE_RESULT,
        )
    channels_ids = [channel.id for channel in ch.chunk]
    start_ind = (ch.ind_chunk - 1) * 10

    await query.message.edit_text(
        text,
        reply_markup=await ik_num_matrix(channels_ids, start_ind, "info"),
    )
    await state.update_data(channels_ids=channels_ids)


@router.callback_query(InfoChannelsState.delete, BackFactory.filter(F.to == "info"))
async def back_info(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await info_channels(query, state, session)


@router.callback_query(InfoChannelsState.info, BackFactory.filter(F.to == "default"))
async def back_channels(
    query: CallbackQuery,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    await fn.state_clear(state)
    await state.set_data(data)

    await state.set_state(CatcherState.actions)

    await query.message.edit_text(
        "Действуй!",
        reply_markup=await ik_action_with_catcher(),
    )


@router.callback_query(InfoChannelsState.add, CancelFactory.filter(F.to == "default"))
async def cancel_add_channels(
    query: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    data_state = await state.get_data()
    ch = Chunker()
    text = await ch(
        model_db=MonitoringChannel,
        session=session,
        ind_chunk=data_state["ind_chunk"],
        func_to_str=pretty_channels,
        if_none_result=IF_NONE_RESULT,
    )

    msg = await query.message.answer(
        text=text,
        reply_markup=await ik_add_or_delete(ch.ind_chunk, ch.quantity_chunks),
    )

    await fn.set_general_message(state, msg)
    await state.set_state(InfoChannelsState.info)
