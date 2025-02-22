# models.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class UserSettings(Base):
    __tablename__ = 'user_settings'

    user_id = Column(Integer, primary_key=True)
    wb_api_key = Column(String)
    notifications_enabled = Column(Boolean, default=False)
    auto_reply_enabled = Column(Boolean, default=False)
    auto_reply_five_stars = Column(Boolean, default=False)
    greeting = Column(String)
    farewell = Column(String)


# Инициализация базы данных
engine = create_engine('sqlite:///bot.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)