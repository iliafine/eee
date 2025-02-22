# keyboards/reviews.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

def review_list_keyboard(reviews: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for review in reviews:
        builder.button(
            text=f"Отзыв #{review['id']}",
            callback_data=f"review_{review['id']}"
        )
    builder.button(text="◀️ Назад", callback_data="auto_reply")
    builder.adjust(1)
    return builder.as_markup()