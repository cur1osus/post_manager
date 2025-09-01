import datetime
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Final

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from bot.db.models import UserDB

logger = logging.getLogger(__name__)

# 777000 is Telegram's user id of service messages
TG_SERVICE_USER_ID: Final[int] = 777000


class WallSubMiddleware(BaseMiddleware):
    async def __call__(  # pyright: ignore
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user: UserDB = data["user"]

        if not user:
            return await handler(event, data)

        sub_active = (
            user.date_sub_start + datetime.timedelta(user.quantity_days_sub)
            > datetime.datetime.now()
        )
        data["sub_active"] = sub_active

        match event.event_type:
            case "message":
                if event.message.text.startswith("/start"):
                    return await handler(event, data)

                if not sub_active:
                    await event.message.answer("Ваша подписка истекла")
                    return
            case _:
                pass

        return await handler(event, data)
