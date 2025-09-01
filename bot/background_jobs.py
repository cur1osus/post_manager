import datetime
import logging
from typing import Final

from aiogram import Bot
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.db.models import Post, UserDB
from bot.utils import fn

logger = logging.getLogger(__name__)
minute: Final[int] = 60


def key_build(key: str) -> str:
    return f"post_manager:func:send_posts:{key}"


key_last_post_id = key_build("last_post_id")


async def send_posts(
    sessionmaker: async_sessionmaker[AsyncSession],
    redis: Redis,
    bot: Bot,
) -> None:
    last_post_id = await redis.get(key_last_post_id)

    async with sessionmaker() as session:
        if last_post_id:
            last_post_id = int(last_post_id)
            posts = (
                await session.scalars(select(Post).where(Post.id > last_post_id))
            ).all()
        else:
            posts = (await session.scalars(select(Post))).all()
            logger.info(posts)

        if not posts:
            return
        await redis.set(key_last_post_id, posts[-1].id)

        users = await session.scalars(
            select(UserDB).where(UserDB.receive_notifications.is_(True))
        )
        if not users:
            logger.info("no users")
            return

        for post in posts:
            useless = True

            for user in users:
                if not await sub_active(user):
                    user.receive_notifications = False
                    continue

                content = post.content.lower()

                matches_ignores = await fn.Text.find_patterns(
                    [i.content for i in user.ignores],
                    content,
                )
                if matches_ignores:
                    logger.info("has ignores")
                    logger.info(f"User ignores: {user.ignores}")
                    continue

                matches_triggers = await fn.Text.find_patterns(
                    [t.content for t in user.triggers],
                    content,
                )

                if not matches_triggers:
                    logger.info("no triggers")
                    logger.info(f"User triggers: {user.triggers}")
                    continue

                link_on_message = fn.Url.message_link_for_channel(
                    channel_username=post.channel_username,
                    text="ссылка на пост",
                    message_id=post.message_id,
                )
                content = await fn.Text.highlight_words(content, matches_triggers)

                await bot.send_message(user.user_id, f"{content} \n\n{link_on_message}")
                useless = False

            if useless:
                await session.delete(post)

        await session.commit()


async def sub_active(user: UserDB) -> bool:
    sub_active = (
        user.date_sub_start + datetime.timedelta(user.quantity_days_sub)
        > datetime.datetime.now()
    )
    return sub_active
