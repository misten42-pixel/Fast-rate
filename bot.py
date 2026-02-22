import os
import re
import time
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from telethon import TelegramClient
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------- MOSCA ----------
MOSCA_USERNAME = "@Mosca67_bot"
TG_API_ID = os.getenv("TG_API_ID")
TG_API_HASH = os.getenv("TG_API_HASH")
TG_STRING_SESSION = os.getenv("TG_STRING_SESSION")

UA = "Mozilla/5.0"
TIMEOUT = 10

@dataclass
class Rate:
    buy: Optional[float]
    sell: Optional[float]

def fmt(x):
    return "—" if x is None else f"{x:.2f}"

# ---------- GRINEX ----------
def fetch_grin
