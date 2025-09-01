from typing import Final
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from bot.db.models import Catcher
from bot.keyboards.factories import (
    ArrowInfoFactory,
    BackFactory,
    CancelFactory,
    CatcherFactory,
    DeleteInfoFactory,
    InfoFactory,
)

LIMIT_BUTTONS: Final[int] = 100
BACK_BUTTON_TEXT = "🔙"


async def ik_admin_panel() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❇️ Добавить Ловца", callback_data="add_new_catcher")
    builder.button(text="👥 Ловцы", callback_data="catchers")
    builder.adjust(1)
    return builder.as_markup()


async def ik_user_panel() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Личный кабинет", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()


async def ik_profile() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text="🟢 Старт", callback_data="start_send_notify")
    builder.button(text="🔴 Стоп", callback_data="stop_send_notify")

    builder.button(text="⚙️ Настроить Игноры", callback_data=InfoFactory(key="ignore"))
    builder.button(
        text="⚙️ Настроить Триггеры", callback_data=InfoFactory(key="trigger")
    )
    builder.button(text="✨ Продлить подписку", callback_data="renew_sub")

    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


async def ik_profile_without_sub() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✨ Продлить подписку", callback_data="renew_sub")

    builder.adjust(1)
    return builder.as_markup()


async def ik_available_catchers(
    catchers: list[Catcher],
    back_to: str = "default",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for catcher in catchers:
        builder.button(
            text=f"{'❇️' if catcher.is_connected else '⛔️'} {catcher.phone} ({catcher.name or '?'})",
            callback_data=CatcherFactory(id=catcher.id),
        )
    builder.button(text=BACK_BUTTON_TEXT, callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_back(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=BACK_BUTTON_TEXT, callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_action_with_catcher(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⛓️‍💥 Отключить", callback_data="disconnect_catcher")
    builder.button(text="💬 Каналы", callback_data=InfoFactory(key="channels"))
    builder.button(text=BACK_BUTTON_TEXT, callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_connect_catcher(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить", callback_data="delete_catcher")
    builder.button(text="❇️ Подключить", callback_data="connect_catcher")
    builder.button(text=BACK_BUTTON_TEXT, callback_data=BackFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_add_or_delete(
    ind_chunk: int,
    quantity_chunks: int,
    back_to: str = "default",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    adjust = []
    if quantity_chunks:
        builder.button(
            text=f"{ind_chunk} / {quantity_chunks}", callback_data="info_about_pages"
        )
        adjust.append(1)
    if quantity_chunks > 1:
        builder.button(
            text="⬅️",
            callback_data=ArrowInfoFactory(to="left"),
        )
        builder.button(
            text="➡️",
            callback_data=ArrowInfoFactory(to="right"),
        )
        adjust.append(2)
    builder.button(text="➕ Добавить", callback_data="add")
    builder.button(text="➖ Удалить", callback_data="delete")
    builder.button(text=BACK_BUTTON_TEXT, callback_data=BackFactory(to=back_to))
    builder.adjust(*adjust, 1, 1, 1)
    return builder.as_markup()


async def ik_cancel_action(back_to: str = "default") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Отмена", callback_data=CancelFactory(to=back_to))
    builder.adjust(1)
    return builder.as_markup()


async def ik_num_matrix(
    ids: list[int],
    start: int,
    back_to: str = "default",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ind, id in enumerate(ids, start):
        builder.button(text=str(ind + 1), callback_data=DeleteInfoFactory(id=id))
    builder.button(text=BACK_BUTTON_TEXT, callback_data=BackFactory(to=back_to))
    q_full_line = len(ids) // 5
    remains = len(ids) % 5
    tail = [remains, 1] if remains else [1]
    builder.adjust(*[5] * q_full_line, *tail)
    return builder.as_markup()
