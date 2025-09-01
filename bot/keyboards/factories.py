from aiogram.filters.callback_data import CallbackData


class BackFactory(CallbackData, prefix="bk"):
    to: str


class CatcherFactory(CallbackData, prefix="c"):
    id: int


class ArrowInfoFactory(CallbackData, prefix="ai"):
    to: str


class CancelFactory(CallbackData, prefix="cn"):
    to: str


class DeleteInfoFactory(CallbackData, prefix="di"):
    id: int


class InfoFactory(CallbackData, prefix="i"):
    key: str
