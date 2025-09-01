import asyncio
import dataclasses
import datetime
import logging
import os
import re
import signal
import subprocess
from collections.abc import Callable
from typing import Any, Final

import psutil
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient
from telethon.errors import (
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.errors.rpcerrorlist import FloodWaitError

from bot.db.models import UserDB
from bot.keyboards.inline import ik_profile, ik_profile_without_sub
from bot.settings import se

logger = logging.getLogger(__name__)

TAIL_PID_FILE = ".pid"
TAIL_LOG_FILE = ".log"


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Result:
    success: bool
    message: str | None


class Function:
    max_length_message: Final[int] = 4000

    @staticmethod
    async def set_general_message(state: FSMContext, message: Message) -> None:
        data_state = await state.get_data()
        message_id = data_state.get("message_id")
        await Function._delete_keyboard(message_id, message)
        await state.update_data(message_id=message.message_id)

    @staticmethod
    async def state_clear(state: FSMContext) -> None:
        new_data = {}
        data_state = await state.get_data()
        for key, value in data_state.items():
            if key == "message_id":
                new_data[key] = value
        await state.clear()
        await state.set_data(new_data)

    @staticmethod
    async def _delete_keyboard(
        message_id_to_delete: int | None, message: Message
    ) -> None:
        if message_id_to_delete:
            try:
                await message.bot.edit_message_reply_markup(
                    chat_id=message.chat.id,
                    message_id=message_id_to_delete,
                    reply_markup=None,
                )
            except:  # noqa
                pass

    @staticmethod
    async def return_profile_text(user: UserDB):
        sub_end = user.date_sub_start + datetime.timedelta(days=user.quantity_days_sub)
        text = (
            f"Профиль\n\n"
            f"Статус получения уведомлений: {'🟢' if user.receive_notifications else '🔴'}\n\n"
            f"Тип подписки: {'ПРОБНЫЙ' if user.quantity_days_sub == 3 else 'ПОЛНЫЙ ПАКЕТ'}\n"
            f"Конец подписки: {sub_end.strftime('%d.%m.%Y')}\n"
        )
        return text

    @staticmethod
    async def return_profile_keyboard(sub_active: bool):
        if sub_active:
            return ik_profile
        return ik_profile_without_sub

    class Manager:
        @staticmethod
        async def start_bot(
            phone: str, path_session: str, api_id: int, api_hash: str
        ) -> int:
            if not os.path.exists(se.script_path):
                logger.error("Bash script not found: %s", se.script_path)
                return -1

            await asyncio.create_subprocess_exec(
                se.script_path,
                path_session,
                str(api_id),
                api_hash,
                phone,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                preexec_fn=os.setpgrp,
                start_new_session=True,
            )

            # Даём скрипту время создать PID-файл
            await asyncio.sleep(1)

            path_pid = os.path.join(se.path_to_folder, f"{phone}{TAIL_PID_FILE}")
            if os.path.exists(path_pid):
                with open(path_pid) as f:
                    pid = int(f.read())
                logger.info(f"Bot started with PID: {pid}")
                return pid
            logger.error(f"PID file not created for {phone}")
            return -1

        @staticmethod
        async def bot_run(phone: str) -> bool:
            path_pid = os.path.join(se.path_to_folder, f"{phone}{TAIL_PID_FILE}")
            if not os.path.exists(path_pid):
                return False
            with open(path_pid) as f:
                pid = int(f.read())
            return psutil.pid_exists(pid)

        @staticmethod
        async def stop_bot(phone: str, delete_session: bool = False) -> None:
            path_pid = os.path.join(se.path_to_folder, f"{phone}{TAIL_PID_FILE}")
            if not os.path.exists(path_pid):
                logger.info("PID-файл не найден")
                return

            with open(path_pid) as f:
                pid = int(f.read())

            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                logger.info(f"Отправлен сигнал завершения процессу с PID: {pid}")
            except ProcessLookupError:
                logger.info("Процесс не найден")
            except PermissionError:
                logger.info("Нет прав на завершение процесса")

            files = [f"{phone}{TAIL_PID_FILE}"]
            if delete_session:
                files.append(f"{phone}.session")
            await Function.Manager.delete_files_by_name(se.path_to_folder, files)

        @staticmethod
        async def delete_files_by_name(folder_path: str, filenames: list[str]) -> None:
            """
            Удаляет файлы с указанными именами в папке.

            :param folder_path: Путь к папке.
            :param filenames: Список имён файлов для удаления (например, ['file1.txt', 'temp.log']).
            """
            if not os.path.exists(folder_path):
                logger.info(f"Папка {folder_path} не существует.")
                return

            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path) and filename in filenames:
                    try:
                        os.remove(file_path)
                        logger.info(f"Удален файл: {file_path}")
                    except Exception as e:
                        logger.info(f"Не удалось удалить {file_path}: {e}")

    class Telethon:
        @staticmethod
        async def create_telethon_session(
            phone: str,
            code: str | int,
            api_id: int,
            api_hash: str,
            phone_code_hash: str,
            password: str | None,
            path: str,
        ) -> Result:
            """
            Асинхронно создает сессию Telethon с авторизацией по коду (и паролю при необходимости).

            :param phone: Номер телефона в международном формате (например, +79991234567)
            :param code: Код из SMS или Telegram
            :param api_id: API ID от my.telegram.org
            :param api_hash: API Hash от my.telegram.org
            :param phone_code_hash: Хеш, полученный при отправке кода
            :param password: Пароль от двухфакторной аутентификации (если включён)
            :param path: Путь к файлу сессии (.session)
            :return: Result(success, message)
            """
            # Валидация входных данных
            if not phone or not phone.lstrip("+").isdigit():
                return Result(success=False, message="invalid_phone")

            if not api_id or not isinstance(api_id, int) or api_id <= 0:
                return Result(success=False, message="invalid_api_id")

            if not api_hash or not isinstance(api_hash, str) or len(api_hash) != 32:
                return Result(success=False, message="invalid_api_hash")

            if not path or not path.endswith(".session"):
                return Result(success=False, message="invalid_path")

            # Приводим code к строке
            code_str = str(code).strip()

            client = None
            try:
                # Создаём клиента
                client = TelegramClient(path, api_id, api_hash)

                await client.connect()
                logger.info(f"Подключение к Telegram для номера {phone}...")

                if await client.is_user_authorized():
                    logger.info("Пользователь уже авторизован.")
                    me = await client.get_me()
                    logger.info(f"Авторизован: {me.first_name} (@{me.username})")
                    return Result(success=True, message=None)

                # Попытка входа
                try:
                    if password:
                        # Уже нужен 2FA — пробуем ввести пароль
                        await client.sign_in(password=password)
                    else:
                        # Вход по коду
                        await client.sign_in(
                            phone=phone, code=code_str, phone_code_hash=phone_code_hash
                        )

                    # Проверяем, авторизовались ли
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        logger.info("Авторизация прошла успешно!")
                        logger.info(f"Пользователь: {me.first_name} (@{me.username})")
                        return Result(success=True, message=None)
                    return Result(success=False, message="auth_failed")

                except PhoneCodeInvalidError:
                    logger.warning(f"Неверный код для номера {phone}.")
                    return Result(success=False, message="invalid_code")

                except PhoneCodeExpiredError:
                    logger.warning(f"Код устарел для номера {phone}.")
                    return Result(success=False, message="code_expired")

                except SessionPasswordNeededError:
                    logger.info(f"Требуется пароль 2FA для номера {phone}.")
                    return Result(success=False, message="password_required")

                except FloodWaitError as e:
                    wait_msg = (
                        f"Ожидание FloodWait: необходимо подождать {e.seconds} секунд."
                    )
                    logger.warning(wait_msg)
                    return Result(success=False, message=f"flood_wait:{e.seconds}")

                except Exception as e:
                    logger.exception(f"Неожиданная ошибка при авторизации: {e}")
                    return Result(success=False, message=f"error:{e!s}")

            except Exception as e:
                logger.exception(f"Критическая ошибка при создании сессии: {e}")
                return Result(success=False, message="critical_error")

            finally:
                # Гарантированное отключение клиента
                if client:
                    try:
                        await client.disconnect()  # pyright: ignore
                    except Exception as e:
                        logger.debug(f"Ошибка при отключении клиента: {e}")

        @staticmethod
        async def send_code_via_telethon(
            phone: str,
            api_id: int,
            api_hash: str,
            path: str,
        ) -> Result:
            """
            Отправляет код подтверждения на указанный номер телефона через Telegram.

            :param phone: Номер телефона в международном формате (например, +79991234567)
            :param api_id: API ID от my.telegram.org
            :param api_hash: API Hash от my.telegram.org
            :param path: Путь к файлу сессии (.session)
            :return: phone_code_hash при успехе, иначе None или специальные строки для разных ошибок
            """
            # Валидация входных данных
            if not phone or not phone.lstrip("+").isdigit():
                logger.warning(f"Неверный формат номера телефона: {phone}")
                return Result(success=False, message="Неверный формат номера телефона")

            if not isinstance(api_id, int) or api_id <= 0:
                logger.warning(f"Неверный API ID: {api_id}")
                return Result(success=False, message="Неверный API ID")

            if not api_hash or not isinstance(api_hash, str) or len(api_hash) != 32:
                logger.warning("Неверный или отсутствующий API Hash.")
                return Result(success=False, message="Неверный API Hash")

            if not path or not path.endswith(".session"):
                logger.warning(f"Некорректный путь к сессии: {path}")
                return Result(success=False, message="Некорректный путь к сессии")

            client = None
            try:
                # Создаём клиент
                client = TelegramClient(path, api_id, api_hash)

                await client.connect()
                logger.info(f"Подключение к Telegram для отправки кода на {phone}...")

                # Проверяем, не авторизован ли уже пользователь
                if await client.is_user_authorized():
                    logger.info(f"Пользователь с номером {phone} уже авторизован.")
                    return Result(success=False, message="Пользователь уже авторизован")

                # Отправляем код
                result = await client.send_code_request(
                    phone=phone,
                    force_sms=False,  # Можно сделать параметром, если нужно
                )

                phone_code_hash = result.phone_code_hash
                logger.info(
                    f"Код подтверждения успешно отправлен на {phone}. Hash: {phone_code_hash[:8]}..."
                )
                return Result(success=True, message=phone_code_hash)

            except PhoneNumberInvalidError:
                logger.warning(f"Неверный номер телефона: {phone}")
                return Result(success=False, message="Неверный номер телефона")

            except PhoneNumberBannedError:
                logger.exception(f"Номер {phone} заблокирован (banned) в Telegram.")
                return Result(success=False, message="Номер заблокирован")

            except SessionPasswordNeededError:
                logger.warning(
                    f"Для номера {phone} требуется пароль (2FA), но сессия не авторизована."
                )
                # Это редкий случай: аккаунт с 2FA, но без активной сессии — обычно после перерегистрации
                return Result(success=False, message="Требуется пароль")

            except FloodWaitError as e:
                wait_msg = f"Ограничение FloodWait: нельзя отправлять код. Подождите {e.seconds} секунд."
                logger.warning(wait_msg)
                # Можно вернуть строку вида `flood_wait:XX`, если хочешь передать время ожидания
                return Result(success=False, message=wait_msg)

            except Exception as e:
                logger.exception(
                    f"Неизвестная ошибка при отправке кода на {phone}: {e}"
                )
                return Result(
                    success=False,
                    message=f"Неизвестная ошибка при отправке кода на {phone}: {e}",
                )

            finally:
                # Гарантированное отключение
                if client:
                    try:
                        await client.disconnect()  # pyright: ignore
                    except Exception as e:
                        logger.debug(f"Ошибка при отключении клиента: {e}")

    class Url:
        @staticmethod
        def message_link_for_chat(chat_id: int, text: str, message_id: int):
            """Generates link to a message, transforming telegram chat id to client peer id."""
            return f'<a href="https://t.me/c/{-(chat_id + 1000000000000)}/{message_id}">{text}</a>'

        @staticmethod
        def message_link_for_channel(channel_username: str, text: str, message_id: int):
            return f'<a href="https://t.me/{channel_username}/{message_id}">{text}</a>'

    class Text:
        @staticmethod
        async def _replace_by_slice(text, start, end, replacement):
            """
            Заменяет подстроку в тексте по индексам среза (start, end) на новую строку.

            :param text: Исходная строка
            :param start: Начальный индекс среза (включительно)
            :param end: Конечный индекс среза (не включительно)
            :param replacement: Строка, на которую нужно заменить
            :return: Новая строка с заменой
            """
            if start < 0:
                start = 0
            if end > len(text):
                end = len(text)
            if start > end:
                raise ValueError("Начальный индекс не может быть больше конечного")

            return text[:start] + replacement + text[end:]

        @staticmethod
        async def find_patterns(words: list[str], text: str) -> list[re.Match[str]]:
            if not words or not text:
                return []

            # Экранируем слова на случай спецсимволов в них, объединяем через |
            escaped_words = "|".join(re.escape(word) for word in words)

            # \b — граница слова, чтобы находить целые слова, а не подстроки
            pattern = rf"\b({escaped_words})\b"

            # Компилируем с флагом IGNORECASE
            regex = re.compile(pattern, re.IGNORECASE)

            return list(regex.finditer(text))

        @staticmethod
        async def highlight_words(
            text: str,
            matches: list[re.Match[str]],
            html_tag: str | None = "b",
            edit_str_func: Callable[[str], str] | None = lambda x: x.upper(),
        ) -> str:
            offset = 0
            for match in matches:
                start, end = match.span()

                if offset:
                    start += offset
                    end += offset

                if html_tag:
                    t = f"<{html_tag}>{match.group()}</{html_tag}>"
                else:
                    t = match.group()

                t = edit_str_func(t) if edit_str_func else t

                text = await Function.Text._replace_by_slice(
                    text,
                    start,
                    end,
                    t,
                )
                offset += len(t) - len(match.group())
            return text


class Chunker:
    async def _get_chunk_recursive(
        self,
        model_db: Any,
        session: AsyncSession,
        ind_chunk: int | None,
        fetched_data: list[Any] | None = None,
    ):
        if fetched_data is None:
            data = (await session.scalars(select(model_db))).all()
        else:
            data = fetched_data

        quantity_chunks = self._count_chunks(len(data))  # всего страниц
        ind_chunk = ind_chunk or quantity_chunks or 1  # текущая страница
        chunk: list[Any] = await self._get_chunk(  # данные о каналах
            list(data),
            ind_chunk=ind_chunk,
        )

        if not chunk and ind_chunk > 1:
            return await self._get_chunk_recursive(
                model_db,
                session,
                ind_chunk - 1,
                list(data),
            )

        self.ind_chunk = ind_chunk
        self.chunk = chunk
        self.quantity_chunks = quantity_chunks

        return chunk

    @staticmethod
    def _count_chunks(len_data: int, chunk_size: int = 10) -> int:
        remains = len_data % chunk_size
        return len_data // chunk_size + (1 if remains else 0)

    @staticmethod
    async def _get_chunk(
        data: list[Any],
        ind_chunk: int,
        chunk_size: int = 10,
    ) -> list[Any]:
        return data[(ind_chunk - 1) * chunk_size : ind_chunk * chunk_size]

    async def __call__(
        self,
        model_db: Any,
        session: AsyncSession,
        ind_chunk: int | None,
        func_to_str: Callable,
        if_none_result: str,
        fetched_data: list[Any] | None = None,
    ) -> Any:
        chunk = await self._get_chunk_recursive(
            model_db=model_db,
            session=session,
            ind_chunk=ind_chunk,
            fetched_data=fetched_data,
        )

        start_numerate = (self.ind_chunk - 1) * 10
        text = await func_to_str(chunk, start_numerate)

        if text is None:
            return if_none_result

        return text
