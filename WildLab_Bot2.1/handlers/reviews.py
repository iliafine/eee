from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from models import Session, UserSettings
from states import ReviewState
from keyboards import back_button, back_button_auto
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

router = Router()
logger = logging.getLogger(__name__)

# ============ Заглушки для интеграций ============

def get_unanswered_reviews(user_id: int):
    """
    Заглушка для получения неотвеченных отзывов пользователя.
    В реальной версии здесь будет запрос к API Wildberries с использованием ключа пользователя.
    Каждый отзыв – это словарь с данными: id, stars, photo, comment, pros, cons.
    """
    return [
        {"id": 101, "stars": 5, "photo": True, "comment": "Отличный продукт!", "pros": "Качество", "cons": ""},
        {"id": 102, "stars": 4, "photo": False, "comment": "Хороший товар", "pros": "Цена", "cons": "Дизайн"},
    ]

def generate_prompt(user: UserSettings, review: dict, arguments: list) -> str:
    """
    Формирует промт для нейросети.
    Если у пользователя заданы фирменное приветствие и прощание, они добавляются.
    """
    greeting = user.greeting if user.greeting else ""
    farewell = user.farewell if user.farewell else ""
    args_text = ", ".join(arguments) if arguments else ""
    return f"{greeting}\nОтзыв: {review['comment']}\nАргументы: {args_text}\n{farewell}"

def generate_reply(prompt: str) -> str:
    """
    Заглушка для генерации ответа через DeepSeek API.
    Здесь будет интеграция с нейросетью, пока возвращаем фиктивный ответ.
    """
    return f"Спасибо за ваш отзыв! Мы ценим ваше мнение."

def send_review_reply(review_id: int, reply: str):
    """
    Заглушка для отправки ответа на отзыв через API Wildberries.
    Здесь будет вызов API для отправки ответа.
    """
    print(f"Отправляем ответ для отзыва {review_id}: {reply}")

# ============ Периодическая проверка отзывов ============

async def check_new_reviews(bot):
    """
    Функция для проверки новых отзывов каждые 5 минут.
    Для каждого пользователя из базы:
      - Получаем неотвеченные отзывы (stub get_unanswered_reviews).
      - Если включены уведомления, отправляем сообщение о новых отзывах.
      - Если включён режим автоответа для 5‑звёздочных отзывов без недостатков, генерируем и отправляем ответ.
    """
    with Session() as session:
        users = session.query(UserSettings).all()
        for user in users:
            try:
                reviews = get_unanswered_reviews(user.user_id)
                if not reviews:
                    continue

                if user.notifications_enabled:
                    await bot.send_message(
                        user.user_id,
                        f"📨 У вас новые отзывы: {len(reviews)}"
                    )

                for review in reviews:
                    if (user.auto_reply_enabled and user.auto_reply_five_stars and
                        review["stars"] == 5 and review["cons"] in ("", None, "-")):
                        prompt = generate_prompt(user, review, [])
                        reply = generate_reply(prompt)
                        send_review_reply(review["id"], reply)
                        await bot.send_message(
                            user.user_id,
                            f"🤖 Автоответ отправлен для отзыва id {review['id']}"
                        )
            except Exception as e:
                logger.error(f"Error processing reviews for user {user.user_id}: {e}")

# ============ Обработка отзывов пользователем ============

@router.callback_query(F.data == "pending_reviews")
async def reviews_list_handler(callback: types.CallbackQuery):
    """
    Выводит список неотвеченных отзывов.
    Каждый отзыв отображается с количеством звёзд, признаком наличия фото, комментарием, достоинствами и недостатками.
    """
    try:
        with Session() as session:
            user = session.get(UserSettings, callback.from_user.id)
            if not user or not user.wb_api_key:
                await callback.message.edit_text(
                    "❌ API-ключ не настроен. Перейдите в настройки, чтобы добавить ключ.",
                    reply_markup=back_button()
                )
                return

        reviews = get_unanswered_reviews(callback.from_user.id)
        if not reviews:
            await callback.message.edit_text("ℹ️ Нет новых отзывов.")
            return

        text = "📢 **Новые отзывы**\n\nВыберите отзыв для ответа:"
        builder = InlineKeyboardBuilder()
        for review in reviews:
            review_text = f"{review['stars']}⭐ | {'📸' if review['photo'] else ''} {review['comment']}"
            builder.button(text=review_text, callback_data=f"review_{review['id']}")
        builder.button(text="◀️ Назад", callback_data="auto_reply")
        builder.adjust(1)
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in reviews_list_handler: {e}")
        await callback.message.edit_text("❌ Произошла ошибка при загрузке отзывов. Попробуйте ещё раз.")

@router.callback_query(F.data.startswith("review_"))
async def review_detail_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    При выборе конкретного отзыва выводим его подробности и просим ввести аргументы для ответа.
    Сохраняем id отзыва и обнуляем счётчик генераций.
    """
    try:
        review_id = int(callback.data.split("_")[1])
        user_id = callback.from_user.id
        reviews = get_unanswered_reviews(user_id)
        review = next((r for r in reviews if r["id"] == review_id), None)
        if not review:
            await callback.message.edit_text("❌ Отзыв не найден.")
            return

        # Формируем текст отзыва
        review_text = f"⭐ {review['stars']}\n"
        if review.get("photo"):
            review_text += f"📸 Фото: {'Да' if review['photo'] else 'Нет'}\n"
        if review.get("comment"):
            review_text += f"💬 Комментарий: {review['comment']}\n"
        if review.get("pros"):
            review_text += f"✅ Достоинства: {review['pros']}\n"
        if review.get("cons"):
            review_text += f"⚠️ Недостатки: {review['cons']}\n"

        # Сохраняем данные отзыва в состоянии
        await state.update_data(review_id=review_id, regeneration_count=0)
        await callback.message.edit_text(
            f"{review_text}\n✍️ Введите аргументы для ответа (через запятую):",
            reply_markup=back_button_auto()
        )
        await state.set_state(ReviewState.waiting_for_arguments)
    except Exception as e:
        logger.error(f"Error in review_detail_handler: {e}")
        await callback.message.edit_text("❌ Произошла ошибка. Попробуйте ещё раз.")

@router.message(ReviewState.waiting_for_arguments)
async def process_review_arguments(message: types.Message, state: FSMContext):
    """
    После ввода аргументов формируем промт, вызываем генерацию ответа и предлагаем варианты действий.
    """
    try:
        arguments = [arg.strip() for arg in message.text.split(",") if arg.strip()]
        await state.update_data(arguments=arguments)

        with Session() as session:
            user = session.get(UserSettings, message.from_user.id)
            if not user:
                await message.answer("❌ Пользователь не найден.")
                return

        data = await state.get_data()
        review_id = data.get("review_id")
        reviews = get_unanswered_reviews(message.from_user.id)
        review = next((r for r in reviews if r["id"] == review_id), None)
        if not review:
            await message.answer("❌ Отзыв не найден.")
            return

        prompt = generate_prompt(user, review, arguments)
        generated_reply = generate_reply(prompt)
        await state.update_data(generated_reply=generated_reply)

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Сгенерировать заново", callback_data="regenerate")
        builder.button(text="✍️ Написать свой ответ", callback_data="write_own")
        builder.button(text="◀️ Назад", callback_data="back_to_reviews")
        builder.adjust(1)

        await message.answer(f"🤖 Ответ:\n{generated_reply}", reply_markup=builder.as_markup())
        await state.set_state(ReviewState.waiting_for_action)
    except Exception as e:
        logger.error(f"Error in process_review_arguments: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте ещё раз.")

@router.callback_query(F.data == "regenerate")
async def regenerate_reply(callback: types.CallbackQuery, state: FSMContext):
    """
    Позволяет сгенерировать новый ответ (до 3 раз).
    """
    try:
        data = await state.get_data()
        count = data.get("regeneration_count", 0)
        if count >= 3:
            await callback.answer("Лимит генерации достигнут. Напишите ответ вручную.", show_alert=True)
            return

        with Session() as session:
            user = session.get(UserSettings, callback.from_user.id)
        reviews = get_unanswered_reviews(callback.from_user.id)
        review = next((r for r in reviews if r["id"] == data.get("review_id")), None)
        arguments = data.get("arguments", [])
        prompt = generate_prompt(user, review, arguments)
        new_reply = generate_reply(prompt)

        await state.update_data(generated_reply=new_reply, regeneration_count=count + 1)

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Сгенерировать заново", callback_data="regenerate")
        builder.button(text="✍️ Написать свой ответ", callback_data="write_own")
        builder.button(text="◀️ Назад", callback_data="back_to_reviews")
        builder.adjust(1)

        await callback.message.edit_text(f"🤖 Ответ:\n{new_reply}", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Error in regenerate_reply: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте ещё раз.", show_alert=True)

@router.callback_query(F.data == "write_own")
async def write_own_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Позволяет пользователю перейти к вводу своего ответа.
    """
    await callback.message.edit_text("✍️ Напишите ваш собственный ответ:", reply_markup=back_button_auto())
    await state.set_state(ReviewState.waiting_for_custom_reply)

@router.message(ReviewState.waiting_for_custom_reply)
async def process_custom_reply(message: types.Message, state: FSMContext):
    """
    Сохраняем введённый пользователем собственный ответ и предлагаем отправить его.
    """
    try:
        custom_reply = message.text
        await state.update_data(generated_reply=custom_reply)

        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Отправить ответ", callback_data="send_reply")
        builder.button(text="◀️ Назад", callback_data="back_to_reviews")
        builder.adjust(1)

        await message.answer(f"🤖 Ваш ответ:\n{custom_reply}", reply_markup=builder.as_markup())
    except Exception as e:
        logger.error(f"Error in process_custom_reply: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте ещё раз.")

@router.callback_query(F.data == "send_reply")
async def send_reply_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Отправляет ответ на отзыв (заглушка).
    Здесь в будущем будет реализована интеграция с API Wildberries для отправки ответа.
    """
    try:
        data = await state.get_data()
        review_id = data.get("review_id")
        reply_text = data.get("generated_reply", "Спасибо за отзыв!")
        send_review_reply(review_id, reply_text)
        logger.info(f"User {callback.from_user.id} sent reply to review {review_id}")

        # Очищаем состояние
        await state.clear()

        await callback.message.edit_text(f"📨 Ответ отправлен для отзыва id {review_id}:\n{reply_text}")
    except Exception as e:
        logger.error(f"Error in send_reply_handler: {e}")
        await callback.message.edit_text("❌ Не удалось отправить ответ. Попробуйте ещё раз.")

@router.callback_query(F.data == "back_to_reviews")
async def back_to_reviews_handler(callback: types.CallbackQuery, state: FSMContext):
    """
    Возвращает пользователя к списку отзывов.
    """
    await state.clear()
    await reviews_list_handler(callback)

# ============ Запуск фоновой задачи ============

async def on_startup(dp):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_new_reviews, 'interval', minutes=5, args=(dp.bot,))
    scheduler.start()

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp, on_startup=on_startup)