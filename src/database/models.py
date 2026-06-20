from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, CheckConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class SystemConfig(Base):
    __tablename__ = 'system_config'
    id = Column(Integer, primary_key=True, autoincrement=True)
    is_first_run = Column(Boolean, default=True)
    bot_name = Column(String, default='Unnamed')
    bot_identity = Column(String, default='digital_mind')
    chat_id = Column(Integer, nullable=True)


class MoodMatrix(Base):
    __tablename__ = 'mood_matrix'
    id = Column(Integer, primary_key=True, autoincrement=True)
    mood = Column(Float, default=0.5)
    fatigue = Column(Float, default=0.0)
    detachment = Column(Float, default=0.3)

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String, CheckConstraint("role IN ('user', 'assistant')"), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class InternalDiary(Base):
    __tablename__ = 'internal_diary'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    raw_thoughts = Column(Text, nullable=True)
    final_output = Column(Text, nullable=True)
    captured_mood = Column(Float, nullable=True)
