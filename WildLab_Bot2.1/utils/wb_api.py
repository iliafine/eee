# utils/wb_api.py
import aiohttp
from models import UserSettings, Session
from config import Config
import logging

logger = logging.getLogger(__name__)


class WildberriesAPI:
    def __init__(self, api_key: str):
        self.base_url = "https://feedbacks-api.wildberries.ru/api/v1"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }

    async def get_unanswered_reviews(self) -> list:
        """Получает непросмотренные отзывы"""
        url = f"{self.base_url}/feedbacks"
        params = {
            "isAnswered": False,
            "take": 5000,
            "skip": 0
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("data", {}).get("feedbacks", [])
                logger.error(f"WB API Error: {await response.text()}")
                return []

    async def send_reply(self, feedback_id: str, text: str) -> bool:
        """Отправляет ответ на отзыв"""
        url = f"{self.base_url}/feedbacks/{feedback_id}/answer"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json={"text": text}) as response:
                return response.status == 200


async def get_unanswered_reviews(user_id: int) -> list:
    with Session() as session:
        user = session.get(UserSettings, user_id)
        if not user or not user.wb_api_key:
            logger.warning(f"User {user_id} has no WB API key configured")
            return []

        wb_api = WildberriesAPI(user.wb_api_key)
        try:
            reviews = await wb_api.get_unanswered_reviews()

            # Логируем ответ от API
            logger.debug(f"API Response: {reviews}")

            if not isinstance(reviews, list):
                logger.error(f"Invalid reviews format: {type(reviews)}")
                return []

            return reviews
        except Exception as e:
            logger.error(f"WB API error: {e}")
            return []