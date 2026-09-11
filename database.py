import aiosqlite
from datetime import datetime, timezone, timedelta

DB_NAME = "src_bot.db"


def today_pht() -> str:
    pht = timezone(timedelta(hours=8))
    return datetime.now(pht).date().isoformat()


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                tokens REAL DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                free_generates_used_today INTEGER DEFAULT 0,
                free_generates_bonus INTEGER DEFAULT 0,
                last_generate_date TEXT,
                easy_owned INTEGER DEFAULT 0,
                medium_owned INTEGER DEFAULT 0,
                hard_owned INTEGER DEFAULT 0,
                referred_by INTEGER,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                accounts_given INTEGER,
                source TEXT,
                given_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS redeem_codes (
                code TEXT PRIMARY KEY,
                tokens INTEGER,
                max_uses INTEGER,
                uses INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS redeemed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                code TEXT,
                tokens INTEGER,
                redeemed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


# ============ USERS ============
async def get_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as c:
            return await c.fetchone()


async def create_user(user_id: int, username: str, first_name: str, referred_by: int = None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, referred_by) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, referred_by)
        )
        await db.commit()


# ============ TOKENS ============
async def add_tokens(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET tokens = tokens + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def deduct_tokens(user_id: int, amount: float):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET tokens = tokens - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


# ============ REFERRALS ============
async def add_referral(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def add_referrals(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET referrals = referrals + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def deduct_referrals(user_id: int, amount: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET referrals = referrals - ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


# ============ FREE GENERATES ============
async def add_free_bonus(user_id: int, amount: int = 1):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET free_generates_bonus = free_generates_bonus + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


async def reset_daily_if_needed(user_id: int) -> bool:
    today = today_pht()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT last_generate_date FROM users WHERE user_id = ?", (user_id,)
        ) as c:
            row = await c.fetchone()

        if not row:
            return False

        if row["last_generate_date"] != today:
            await db.execute(
                "UPDATE users SET free_generates_used_today = 0, last_generate_date = ? WHERE user_id = ?",
                (today, user_id)
            )
            await db.commit()
            return True
    return False


async def use_free_generate(user_id: int):
    today = today_pht()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """UPDATE users 
               SET free_generates_used_today = free_generates_used_today + 1,
                   last_generate_date = ?
               WHERE user_id = ?""",
            (today, user_id)
        )
        await db.commit()


async def add_owned(user_id: int, category: str, amount: int = 1):
    column = f"{category}_owned"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            f"UPDATE users SET {column} = {column} + ? WHERE user_id = ?",
            (amount, user_id)
        )
        await db.commit()


# ============ HISTORY ============
async def log_history(user_id: int, category: str, count: int, source: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO history (user_id, category, accounts_given, source) VALUES (?, ?, ?, ?)",
            (user_id, category, count, source)
        )
        await db.commit()


# ============ REDEEM CODES ============
async def create_redeem_code(code: str, tokens: int, max_uses: int, admin_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO redeem_codes (code, tokens, max_uses, created_by) VALUES (?, ?, ?, ?)",
            (code, tokens, max_uses, admin_id)
        )
        await db.commit()


async def get_redeem_code(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM redeem_codes WHERE code = ?", (code,)) as c:
            return await c.fetchone()


async def use_redeem_code(code: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE redeem_codes SET uses = uses + 1 WHERE code = ?", (code,)
        )
        await db.commit()


async def log_redeem(user_id: int, code: str, tokens: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO redeemed (user_id, code, tokens) VALUES (?, ?, ?)",
            (user_id, code, tokens)
        )
        await db.commit()


async def has_redeemed(user_id: int, code: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM redeemed WHERE user_id = ? AND code = ?",
            (user_id, code)
        ) as c:
            return await c.fetchone() is not None


# ============ BANS ============
async def ban_user(user_id: int, reason: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET is_banned = 1, ban_reason = ? WHERE user_id = ?",
            (reason, user_id)
        )
        await db.commit()


async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET is_banned = 0, ban_reason = NULL WHERE user_id = ?",
            (user_id,)
        )
        await db.commit()


async def is_banned(user_id: int) -> bool:
    user = await get_user(user_id)
    if not user:
        return False
    return bool(user["is_banned"])


# ============ ADMIN ============
async def get_all_users():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as c:
            return await c.fetchall()


async def get_top_referrers(limit: int = 10):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT user_id, first_name, username, referrals, tokens
               FROM users
               WHERE referrals > 0 AND is_banned = 0
               ORDER BY referrals DESC
               LIMIT ?""",
            (limit,)
        ) as c:
            return await c.fetchall()