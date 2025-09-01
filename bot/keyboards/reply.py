from aiogram.utils.keyboard import ReplyKeyboardBuilder


async def rk_cancel():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Отмена")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)
