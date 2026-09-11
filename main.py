import asyncio
import logging
import os
import secrets
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import (
    BOT_TOKEN, ADMIN_IDS, REQUIRED_CHANNELS,
    FREE_LINES_PER_GENERATE, FREE_DAILY_LIMIT, FREE_REFERRAL_BONUS,
    PAID_PRICES, STOCK_FILES, TOKEN_PRICE_PHP,
    GCASH_NUMBER, GCASH_NAME, GCASH_QR_PATH, GCASH_QR_FILE_ID,
    WELCOME_MESSAGE, BUY_TOKENS_MESSAGE, SUPPORT_MESSAGE,
)
from database import *
from keyboards import *

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()

# Temp storage para sa admin states
ADMIN_STATES = {}


# ============ HELPERS ============

async def check_membership(user_id: int) -> bool:
    for ch in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=ch["id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logging.warning(f"Cannot check {ch['id']}: {e}")
            continue
    return True


def count_lines(category: str) -> int:
    path = STOCK_FILES.get(category)
    if not path or not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        return len([l for l in f.readlines() if l.strip()])


def take_lines(category: str, count: int) -> list[str]:
    path = STOCK_FILES.get(category)
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f.readlines() if l.strip()]
    taken = lines[:count]
    remaining = lines[count:]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(remaining))
    return taken


def get_user_free_info(user) -> dict:
    today = today_pht()
    last_date = user["last_generate_date"]
    used_today = user["free_generates_used_today"] if last_date == today else 0
    bonus = user["free_generates_bonus"]
    daily_limit = FREE_DAILY_LIMIT + bonus
    remaining = max(0, daily_limit - used_today)
    return {
        "daily_limit": daily_limit,
        "used_today": used_today,
        "remaining": remaining,
        "bonus": bonus,
    }


async def send_qr(target, caption: str, markup=None):
    if GCASH_QR_FILE_ID:
        try:
            await target.answer_photo(photo=GCASH_QR_FILE_ID, caption=caption, reply_markup=markup)
            return
        except Exception:
            pass
    if os.path.exists(GCASH_QR_PATH):
        try:
            await target.answer_photo(photo=FSInputFile(GCASH_QR_PATH), caption=caption, reply_markup=markup)
            return
        except Exception:
            pass
    await target.answer(caption, reply_markup=markup)


# ============ START ============

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""

    args = message.text.split()
    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
            if ref_id != user_id:
                referred_by = ref_id
        except ValueError:
            pass

    existing = await get_user(user_id)
    is_new = existing is None

    await create_user(user_id, username, first_name, referred_by)

    # Referral rewards
    if is_new and referred_by:
        referrer = await get_user(referred_by)
        if referrer:
            await add_referral(referred_by)
            await add_free_bonus(referred_by, FREE_REFERRAL_BONUS)
            try:
                await bot.send_message(
                    referred_by,
                    f"🎉 **Bagong Referral!**\n\n"
                    f"👤 {first_name} (@{username}) ay sumali gamit ang link mo.\n"
                    f"🎁 +{FREE_REFERRAL_BONUS} free generate access!"
                )
            except:
                pass

    await reset_daily_if_needed(user_id)
    user = await get_user(user_id)

    # Ban check
    if user["is_banned"]:
        await message.answer(
            f"🚫 **BANNED KA**\n\n"
            f"📝 Reason: {user['ban_reason'] or 'Violation of rules'}\n\n"
            f"Kung may tanong, DM @BEGSHARK"
        )
        return

    # Channel buttons
    channel_buttons = []
    for ch in REQUIRED_CHANNELS:
        channel_buttons.append([
            InlineKeyboardButton(text=ch["name"], url=ch["url"])
        ])

    welcome_kb = InlineKeyboardMarkup(inline_keyboard=channel_buttons)

    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=welcome_kb,
        disable_web_page_preview=True
    )

    await message.answer(
        "👇 **Pumili sa menu sa ibaba:**",
        reply_markup=main_menu()
    )


# ============ FREE TXT ============

@dp.message(F.text == "🎁 Free TXT")
async def free_txt(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await message.answer("⚠️ Mag /start muna.")
        return

    if user["is_banned"]:
        await message.answer(
            f"🚫 **Banned ka!**\n\n"
            f"📝 Reason: {user['ban_reason'] or 'Violation'}"
        )
        return

    if not await check_membership(user_id):
        await message.answer(
            "⚠️ **Kailangan mo munang sumali sa mga channels:**\n\n"
            "Pagkatapos sumali, i-click ang ✅ Verify Join.",
            reply_markup=join_channels_kb()
        )
        return

    await reset_daily_if_needed(user_id)
    user = await get_user(user_id)
    info = get_user_free_info(user)

    if info["remaining"] <= 0:
        bot_info = await bot.get_me()
        ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
        await message.answer(
            f"❌ **Ubos na ang free generates mo ngayong araw!**\n\n"
            f"📊 Nagamit ngayon: `{info['used_today']}/{info['daily_limit']}`\n"
            f"⏰ **Mag-reset bukas ng 12:00 AM PHT**\n\n"
            f"💡 **Paano makakuha pa ngayon?**\n"
            f"• Mag-refer ng friend → **+1 permanent bonus**\n"
            f"• Bumili ng paid accounts sa 🛒 Buy Accounts\n\n"
            f"🔗 **Referral link:**\n`{ref_link}`"
        )
        return

    available = count_lines("free")
    if available < FREE_LINES_PER_GENERATE:
        await message.answer(
            f"😔 **Hindi sapat ang stock!**\n\n"
            f"Available: `{available}` lines\n"
            f"Kailangan: `{FREE_LINES_PER_GENERATE}` lines"
        )
        return

    accounts = take_lines("free", FREE_LINES_PER_GENERATE)
    await use_free_generate(user_id)
    await log_history(user_id, "free", len(accounts), "free_generate")

    filename = f"free_{user_id}_{len(accounts)}_accounts.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(accounts))

    await message.answer_document(
        FSInputFile(filename),
        caption=(
            f"🎉 **Free Accounts Generated!**\n\n"
            f"📦 Accounts: `{len(accounts)}`\n"
            f"📊 Nagamit ngayon: `{info['used_today'] + 1}/{info['daily_limit']}`\n"
            f"⏰ Remaining today: `{info['remaining'] - 1}`\n\n"
            f"⚠️ Huwag ibahagi. Walang refund."
        )
    )
    os.remove(filename)


@dp.callback_query(F.data == "verify_join")
async def verify_join(callback: CallbackQuery):
    if await check_membership(callback.from_user.id):
        await callback.answer("✅ Verified!", show_alert=True)
        await callback.message.delete()
        await callback.message.answer(
            "✅ Verified! Pwede ka nang kumuha ng Free TXT.",
            reply_markup=main_menu()
        )
    else:
        await callback.answer("❌ Hindi ka pa sumali sa lahat!", show_alert=True)


# ============ BUY ACCOUNTS ============

@dp.message(F.text == "🛒 Buy Accounts")
async def buy_accounts(message: Message):
    user = await get_user(message.from_user.id)

    if user and user["is_banned"]:
        await message.answer("🚫 Banned ka.")
        return

    text = f"""
🛒 **Buy Accounts**

👥 **Iyong referrals:** `{user['referrals']}`
━━━━━━━━━━━━━━━━━━

🟢 **Easy** — {PAID_PRICES['easy']} referrals
   • Stock: `{count_lines('easy')}`
   • Owned: `{user['easy_owned']}`

🟡 **Medium** — {PAID_PRICES['medium']} referrals
   • Stock: `{count_lines('medium')}`
   • Owned: `{user['medium_owned']}`

🔴 **Hard** — {PAID_PRICES['hard']} referrals
   • Stock: `{count_lines('hard')}`
   • Owned: `{user['hard_owned']}`

━━━━━━━━━━━━━━━━━━
Pumili:
"""
    await message.answer(text, reply_markup=shop_kb())


@dp.callback_query(F.data.startswith("buy_"))
async def buy_account(callback: CallbackQuery):
    category = callback.data.replace("buy_", "")
    if category not in PAID_PRICES:
        await callback.answer("Invalid!")
        return

    user_id = callback.from_user.id
    user = await get_user(user_id)

    if user["is_banned"]:
        await callback.answer("🚫 Banned ka!", show_alert=True)
        return

    price = PAID_PRICES[category]

    if user["referrals"] < price:
        await callback.answer(
            f"❌ Kulang referrals!\nKailangan: {price}\nIyo: {user['referrals']}",
            show_alert=True
        )
        return

    if count_lines(category) < 1:
        await callback.answer("😔 Out of stock!", show_alert=True)
        return

    accounts = take_lines(category, 1)
    if not accounts:
        await callback.answer("😔 Out of stock!", show_alert=True)
        return

    await deduct_referrals(user_id, price)
    await add_owned(user_id, category, 1)
    await log_history(user_id, category, 1, "paid_purchase")

    await callback.message.answer(
        f"✅ **Purchase Successful!**\n\n"
        f"📦 Category: **{category.upper()}**\n"
        f"💸 Nagastos: `{price} referrals`\n\n"
        f"🎁 **Iyong account:**\n"
        f"```\n{accounts[0]}\n```"
    )
    await callback.answer("✅ Success!")


# ============ BUY TOKENS ============

@dp.message(F.text == "💰 Buy Tokens")
async def buy_tokens(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if user and user["is_banned"]:
        await message.answer("🚫 Banned ka.")
        return

    await send_qr(
        message,
        BUY_TOKENS_MESSAGE.format(
            gcash_number=GCASH_NUMBER,
            gcash_name=GCASH_NAME
        )
    )


@dp.message(F.photo)
async def handle_payment_screenshot(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        return

    if user["is_banned"]:
        await message.answer("🚫 Banned ka.")
        return

    # Admin → capture file_id
    if user_id in ADMIN_IDS:
        file_id = message.photo[-1].file_id
        await message.answer(
            f"✅ **File ID:**\n\n`GCASH_QR_FILE_ID = \"{file_id}\"`"
        )
        return

    file_id = message.photo[-1].file_id

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                photo=file_id,
                caption=(
                    f"💳 **Payment Screenshot**\n\n"
                    f"👤 User: {user['first_name']} (@{user['username']})\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"💰 Tokens: `{user['tokens']:.2f}`\n"
                    f"👥 Referrals: `{user['referrals']}`\n\n"
                    f"⚠️ **I-verify kung legit!**\n"
                    f"Para mag-approve:\n"
                    f"`/addtokens {user_id} <amount>`\n\n"
                    f"Para mag-ban kung fake:\n"
                    f"`/ban {user_id} Fake receipt`"
                )
            )
        except Exception as e:
            logging.warning(f"Cannot forward to admin {admin_id}: {e}")

    await message.answer(
        "✅ **Natanggap na ang screenshot!**\n\n"
        "⏳ Hintayin ang approval ng admin (5-30 mins).\n\n"
        "⚠️ **PAALALA:** Kung fake ang receipt mo, "
        "automatic BAN ka agad!"
    )


# ============ LEADERBOARD ============

def build_leaderboard_text(users, current_user_id: int = None) -> str:
    medals = ["🥇", "🥈", "🥉"]

    text = "🏆 **LEADERBOARD — Top Referrers**\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"

    if not users:
        text += "😔 Wala pang referrals. Ikaw ang mauna!\n"
        return text

    for i, u in enumerate(users):
        rank = medals[i] if i < 3 else f"`#{i+1}`"
        name = u["first_name"] or "Unknown"
        username = f"@{u['username']}" if u["username"] else ""
        refs = u["referrals"]

        marker = " ⬅️ **IKAW**" if current_user_id and u["user_id"] == current_user_id else ""

        text += f"{rank} **{name}** {username}\n"
        text += f"   👥 `{refs}` referrals{marker}\n\n"

    text += "━━━━━━━━━━━━━━━━━━\n"
    text += "💡 **Mag-refer pa para umakyat sa ranking!**"
    return text


@dp.message(F.text == "🏆 Leaderboard")
async def leaderboard(message: Message):
    user_id = message.from_user.id

    if await is_banned(user_id):
        await message.answer("🚫 Banned ka.")
        return

    users = await get_top_referrers(10)
    text = build_leaderboard_text(users, user_id)
    await message.answer(text, reply_markup=leaderboard_kb())


@dp.callback_query(F.data == "lb_refresh")
async def lb_refresh(callback: CallbackQuery):
    user_id = callback.from_user.id
    users = await get_top_referrers(10)
    text = build_leaderboard_text(users, user_id)
    await callback.message.edit_text(text, reply_markup=leaderboard_kb())
    await callback.answer("🔄 Refreshed!")


@dp.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message):
    user_id = message.from_user.id
    users = await get_top_referrers(10)
    text = build_leaderboard_text(users, user_id)
    await message.answer(text, reply_markup=leaderboard_kb())


# ============ STATUS VIEWER ============

@dp.message(F.text == "📊 My Status")
async def my_status(message: Message):
    user_id = message.from_user.id
    await reset_daily_if_needed(user_id)
    user = await get_user(user_id)
    info = get_user_free_info(user)

    text = f"""
📊 **Iyong Status**

━━━━━━━━━━━━━━━━━━
👥 **Referrals:** `{user['referrals']}`

🎁 **FREE (Daily):**
• Daily limit: `{FREE_DAILY_LIMIT}`
• Referral bonus: `+{info['bonus']}`
• Total limit today: `{info['daily_limit']}`
• Nagamit ngayon: `{info['used_today']}`
• **Remaining today:** `{info['remaining']}`
• Lines per generate: `{FREE_LINES_PER_GENERATE}`

🛒 **PAID ACCOUNTS OWNED:**
• Easy: `{user['easy_owned']}`
• Medium: `{user['medium_owned']}`
• Hard: `{user['hard_owned']}`

━━━━━━━━━━━━━━━━━━
📦 **STOCKS AVAILABLE:**
• Free: `{count_lines('free')}` lines
• Easy: `{count_lines('easy')}`
• Medium: `{count_lines('medium')}`
• Hard: `{count_lines('hard')}`

⏰ Reset daily generates: **12:00 AM PHT**
"""
    await message.answer(text)


# ============ MY ACCOUNTS ============

@dp.message(F.text == "📦 My Accounts")
async def my_accounts(message: Message):
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT category, accounts_given, source, given_at 
               FROM history 
               WHERE user_id = ? 
               ORDER BY given_at DESC 
               LIMIT 20""",
            (user_id,)
        ) as c:
            rows = await c.fetchall()

    if not rows:
        await message.answer("📦 **Wala ka pang accounts.**\n\nGamitin ang 🎁 Free TXT o 🛒 Buy Accounts.")
        return

    text = "📦 **Recent Accounts (Last 20)**\n\n━━━━━━━━━━━━━━━━━━\n\n"

    for r in rows:
        emoji = "🎁" if r["source"] == "free_generate" else "🛒"
        text += f"{emoji} **{r['category'].upper()}** — `{r['accounts_given']}` accounts\n"
        text += f"   📅 {r['given_at']}\n\n"

    text += "━━━━━━━━━━━━━━━━━━\n"
    text += "💡 Kung nawala ang accounts, hindi na maibabalik."

    await message.answer(text)


# ============ REFERRALS ============

@dp.message(F.text == "👥 Referrals")
async def referrals(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    await message.answer(
        f"👥 **Referral Program**\n\n"
        f"🎁 **Reward:** +1 free generate access (permanent)\n"
        f"👥 **Iyong referrals:** `{user['referrals']}`\n\n"
        f"🔗 **Iyong link:**\n`{ref_link}`\n\n"
        f"📤 I-share sa friends mo!"
    )


# ============ PROFILE ============

@dp.message(F.text == "👤 Profile")
async def profile(message: Message):
    user = await get_user(message.from_user.id)
    info = get_user_free_info(user)
    await message.answer(
        f"👤 **Profile**\n\n"
        f"🆔 ID: `{user['user_id']}`\n"
        f"📛 Name: {user['first_name']}\n"
        f"👤 Username: @{user['username'] or 'none'}\n"
        f"👥 Referrals: `{user['referrals']}`\n"
        f"🎁 Free generates left today: `{info['remaining']}`\n"
        f"📅 Joined: {user['joined_at']}"
    )


# ============ SUPPORT ============

@dp.message(F.text == "📞 Support")
async def support(message: Message):
    await message.answer(SUPPORT_MESSAGE)


# ============ USER COMMANDS ============

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("⚠️ Mag /start muna.")
        return

    await message.answer(
        f"💰 **Iyong Balance**\n\n"
        f"💳 Tokens: **`{user['tokens']:.2f}`**\n"
        f"👥 Referrals: **`{user['referrals']}`**\n\n"
        f"💡 **Paano mag-top up?**\n"
        f"• Mag-redeem ng code: `/redeem <CODE>`\n"
        f"• Bumili ng tokens: 💰 Buy Tokens"
    )


@dp.message(Command("acc"))
async def cmd_acc_status(message: Message):
    user_id = message.from_user.id
    await reset_daily_if_needed(user_id)
    user = await get_user(user_id)

    if not user:
        await message.answer("⚠️ Mag /start muna.")
        return

    info = get_user_free_info(user)

    await message.answer(
        f"📊 **Account Status**\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 **User Info**\n"
        f"• ID: `{user['user_id']}`\n"
        f"• Name: {user['first_name']}\n"
        f"• Username: @{user['username'] or 'none'}\n"
        f"• Joined: {user['joined_at']}\n"
        f"• Banned: {'🚫 Yes' if user['is_banned'] else '✅ No'}\n\n"
        f"💰 **Balance**\n"
        f"• Tokens: `{user['tokens']:.2f}`\n"
        f"• Referrals: `{user['referrals']}`\n\n"
        f"🎁 **Free Generates (Daily)**\n"
        f"• Limit today: `{info['daily_limit']}`\n"
        f"• Used today: `{info['used_today']}`\n"
        f"• Remaining: `{info['remaining']}`\n"
        f"• Permanent bonus: `+{info['bonus']}`\n\n"
        f"🛒 **Paid Accounts Owned**\n"
        f"• 🟢 Easy: `{user['easy_owned']}`\n"
        f"• 🟡 Medium: `{user['medium_owned']}`\n"
        f"• 🔴 Hard: `{user['hard_owned']}`"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        f"📖 **Bot Guide**\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎁 **FREE ACCOUNTS**\n"
        f"• {FREE_DAILY_LIMIT} generates per day (reset 12 AM PHT)\n"
        f"• {FREE_LINES_PER_GENERATE} accounts kada generate\n"
        f"• +1 permanent bonus kada referral\n"
        f"• Kailangan sumali sa channels\n\n"
        f"🛒 **PAID ACCOUNTS (Referral-based)**\n"
        f"• 🟢 Easy — {PAID_PRICES['easy']} referrals\n"
        f"• 🟡 Medium — {PAID_PRICES['medium']} referrals\n"
        f"• 🔴 Hard — {PAID_PRICES['hard']} referrals\n\n"
        f"💰 **TOKENS**\n"
        f"• 1 token = ₱{TOKEN_PRICE_PHP}\n"
        f"• Mag-redeem gamit: `/redeem <CODE>`\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📋 **COMMANDS**\n"
        f"• /start — simulan ang bot\n"
        f"• /balance — tingnan balance\n"
        f"• /acc — account status\n"
        f"• /redeem `<code>` — mag-redeem ng tokens\n"
        f"• /leaderboard — top referrers\n"
        f"• /help — itong guide\n\n"
        f"📞 **Support:** @BEGSHARK"
    )


@dp.message(Command("redeem"))
async def redeem_code(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ **Usage:** `/redeem <CODE>`\n\n"
            "Halimbawa: `/redeem SRC-A1B2C3D4`"
        )
        return

    code = parts[1].upper()
    user_id = message.from_user.id

    if await is_banned(user_id):
        await message.answer("🚫 **Banned ka.** Hindi ka pwedeng mag-redeem.")
        return

    if not await get_user(user_id):
        await message.answer("⚠️ Mag /start muna.")
        return

    code_data = await get_redeem_code(code)
    if not code_data:
        await message.answer("❌ **Invalid code!**")
        return

    if code_data["uses"] >= code_data["max_uses"]:
        await message.answer("❌ **Expired na ang code!**")
        return

    if await has_redeemed(user_id, code):
        await message.answer("❌ **Na-redeem mo na ang code na ito!**")
        return

    await use_redeem_code(code)
    await add_tokens(user_id, code_data["tokens"])
    await log_redeem(user_id, code, code_data["tokens"])

    user = await get_user(user_id)
    await message.answer(
        f"🎉 **Code Redeemed!**\n\n"
        f"🔑 Code: `{code}`\n"
        f"💰 Nakuha mo: **+{code_data['tokens']} tokens**\n"
        f"💳 New balance: `{user['tokens']:.2f} tokens`"
    )


# ============ ADMIN COMMANDS ============

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = await get_all_users()
    await message.answer(
        f"👑 **Admin Panel**\n\n"
        f"👥 Total users: `{len(users)}`\n\n"
        f"**Commands:**\n"
        f"`/generate <tokens> [uses]` — gumawa redeem code\n"
        f"`/addstock <category>` — mag-add stocks\n"
        f"`/addtokens <id> <amt>` — dagdagan tokens\n"
        f"`/addref <id> <amt>` — dagdagan referrals\n"
        f"`/addfree <id> <amt>` — dagdagan free generates\n"
        f"`/ban <id> [reason]` — i-ban user\n"
        f"`/unban <id>` — i-unban user\n"
        f"`/stock` — tingnan stocks\n"
        f"`/broadcast <msg>` — message lahat"
    )


@dp.message(Command("generate"))
async def admin_generate_code(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        tokens = int(parts[1])
        uses = int(parts[2]) if len(parts) > 2 else 1

        code = "SRC-" + secrets.token_hex(4).upper()
        await create_redeem_code(code, tokens, uses, message.from_user.id)

        await message.answer(
            f"🎟️ **Redeem Code Generated**\n\n"
            f"🔑 Code: `{code}`\n"
            f"💰 Tokens: **{tokens}**\n"
            f"👥 Max uses: **{uses}**\n\n"
            f"📤 I-share sa users."
        )
    except:
        await message.answer("❌ Usage: `/generate <tokens> [uses]`")


@dp.message(Command("addtokens"))
async def admin_add_tokens(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        target = int(parts[1])
        amount = float(parts[2])
        await add_tokens(target, amount)
        await message.answer(f"✅ Added {amount} tokens to {target}")
        try:
            await bot.send_message(target, f"🎉 Nadagdag: **+{amount} tokens**!")
        except:
            pass
    except:
        await message.answer("Usage: `/addtokens <user_id> <amount>`")


@dp.message(Command("addref"))
async def admin_add_ref(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        target = int(parts[1])
        amount = int(parts[2])
        await add_referrals(target, amount)
        await message.answer(f"✅ Added {amount} referrals to {target}")
    except:
        await message.answer("Usage: `/addref <user_id> <amount>`")


@dp.message(Command("addfree"))
async def admin_add_free(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        target = int(parts[1])
        amount = int(parts[2])
        await add_free_bonus(target, amount)
        await message.answer(f"✅ Added {amount} free generates to {target}")
    except:
        await message.answer("Usage: `/addfree <user_id> <amount>`")


@dp.message(Command("stock"))
async def admin_stock(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        f"📦 **Stock Levels**\n\n"
        f"🎁 Free: `{count_lines('free')}` lines\n"
        f"🟢 Easy: `{count_lines('easy')}`\n"
        f"🟡 Medium: `{count_lines('medium')}`\n"
        f"🔴 Hard: `{count_lines('hard')}`"
    )


@dp.message(Command("addstock"))
async def admin_add_stock(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ **Usage:** `/addstock <category>`\n\n"
            "Categories: `free`, `easy`, `medium`, `hard`"
        )
        return

    category = parts[1].lower()
    if category not in STOCK_FILES:
        await message.answer(f"❌ Invalid! Pumili sa: {', '.join(STOCK_FILES.keys())}")
        return

    await message.answer(
        f"📦 **Add Stock: {category.upper()}**\n\n"
        f"I-send mo na ngayon ang accounts (isang linya bawat isa).\n\n"
        f"Format:\n"
        f"```\n"
        f"user1:pass1\n"
        f"user2:pass2\n"
        f"```"
    )

    ADMIN_STATES[message.from_user.id] = {"action": "addstock", "category": category}


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_admin_stock_input(message: Message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return

    state = ADMIN_STATES.get(user_id)
    if not state or state.get("action") != "addstock":
        return

    # Skip kung menu button
    menu_buttons = [
        "🎁 Free TXT", "🛒 Buy Accounts", "💰 Buy Tokens", "🏆 Leaderboard",
        "👥 Referrals", "📊 My Status", "💰 Balance", "📦 My Accounts",
        "👤 Profile", "📞 Support"
    ]
    if message.text in menu_buttons:
        return

    category = state["category"]
    lines = [l.strip() for l in message.text.split("\n") if l.strip()]

    if not lines:
        await message.answer("❌ Walang laman. Subukan ulit.")
        return

    path = STOCK_FILES[category]
    with open(path, "a", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    del ADMIN_STATES[user_id]

    total = count_lines(category)
    await message.answer(
        f"✅ **Stock Added!**\n\n"
        f"📦 Category: **{category.upper()}**\n"
        f"➕ Added: **{len(lines)}** accounts\n"
        f"📊 Total stock: **{total}** accounts"
    )


@dp.message(Command("ban"))
async def admin_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split(maxsplit=2)
        target_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Violation of rules"

        target = await get_user(target_id)
        if not target:
            await message.answer(f"❌ User `{target_id}` not found.")
            return

        await ban_user(target_id, reason)
        await message.answer(
            f"🚫 **User Banned**\n\n"
            f"👤 User: `{target_id}`\n"
            f"📝 Reason: {reason}"
        )

        try:
            await bot.send_message(
                target_id,
                f"🚫 **Na-ban ka!**\n\n"
                f"📝 Reason: {reason}\n\n"
                f"DM @BEGSHARK kung may tanong."
            )
        except:
            pass
    except:
        await message.answer("❌ Usage: `/ban <user_id> [reason]`")


@dp.message(Command("unban"))
async def admin_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    try:
        parts = message.text.split()
        target_id = int(parts[1])

        await unban_user(target_id)
        await message.answer(f"✅ **User Unbanned**\n\n👤 User: `{target_id}`")

        try:
            await bot.send_message(target_id, "✅ Na-unban ka na!")
        except:
            pass
    except:
        await message.answer("❌ Usage: `/unban <user_id>`")


@dp.message(Command("broadcast"))
async def admin_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text.replace("/broadcast", "").strip()
    if not text:
        await message.answer("Usage: `/broadcast <msg>`")
        return
    users = await get_all_users()
    sent = 0
    for u in users:
        try:
            await bot.send_message(u["user_id"], f"📢 **Announcement**\n\n{text}")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Sent to {sent}/{len(users)}")


# ============ MAIN ============

async def main():
    await init_db()
    os.makedirs("stocks", exist_ok=True)
    os.makedirs("assets", exist_ok=True)

    for cat, path in STOCK_FILES.items():
        if not os.path.exists(path):
            open(path, "w").close()

    print("🤖 ZZEY BOT GEN is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())