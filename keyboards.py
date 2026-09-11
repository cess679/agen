from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from config import REQUIRED_CHANNELS, PAID_PRICES


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎁 Free TXT"),     KeyboardButton(text="🛒 Buy Accounts")],
            [KeyboardButton(text="💰 Buy Tokens"),   KeyboardButton(text="🏆 Leaderboard")],
            [KeyboardButton(text="👥 Referrals"),    KeyboardButton(text="📊 My Status")],
            [KeyboardButton(text="💰 Balance"),      KeyboardButton(text="📦 My Accounts")],
            [KeyboardButton(text="👤 Profile"),      KeyboardButton(text="📞 Support")],
        ],
        resize_keyboard=True
    )


def join_channels_kb():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append([InlineKeyboardButton(text=ch["name"], url=ch["url"])])
    buttons.append([InlineKeyboardButton(text="✅ Verify Join", callback_data="verify_join")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shop_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🟢 Easy — {PAID_PRICES['easy']} referrals",
            callback_data="buy_easy"
        )],
        [InlineKeyboardButton(
            text=f"🟡 Medium — {PAID_PRICES['medium']} referrals",
            callback_data="buy_medium"
        )],
        [InlineKeyboardButton(
            text=f"🔴 Hard — {PAID_PRICES['hard']} referrals",
            callback_data="buy_hard"
        )],
    ])


def leaderboard_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="lb_refresh")],
    ])