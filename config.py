import os
from dotenv import load_dotenv

load_dotenv()

# ============ BOT ============
BOT_TOKEN = os.getenv("8833347370:AAEeu4KMO7iW_zlbFLxLXmmUIe1pxiZKgN0")

# ============ ADMIN ============
ADMIN_IDS = [8597996592]

# ============ REQUIRED CHANNELS ============
REQUIRED_CHANNELS = [
    {"id": "@channel1", "name": "📢 Channel 1", "url": "https://t.me/forsaleee_xyss"},
    {"id": "@channel2", "name": "📢 Channel 2", "url": "https://t.me/yearner_ng_taon"},
]
# 👆 PALITAN MO ITO

# ============ FREE USER SETTINGS ============
FREE_LINES_PER_GENERATE = 500
FREE_DAILY_LIMIT = 10
FREE_REFERRAL_BONUS = 1

# ============ PAID USER SETTINGS ============
PAID_PRICES = {
    "easy":   10,
    "medium": 20,
    "hard":   30,
}

# ============ TOKEN PRICING ============
TOKEN_PRICE_PHP = 2

# ============ GCASH ============
GCASH_NUMBER = "09XXXXXXXXX"
GCASH_NAME = "Your Name"
GCASH_QR_PATH = "assets/gcash_qr.png"
GCASH_QR_FILE_ID = ""

# ============ STOCK FILES ============
STOCK_FILES = {
    "free":   "stocks/free.txt",
    "easy":   "stocks/easy_paid.txt",
    "medium": "stocks/medium_paid.txt",
    "hard":   "stocks/hard_paid.txt",
}

# ============ CUSTOM MESSAGES ============
WELCOME_MESSAGE = """
🎉 **WELCOME TO ZZEY BOT GEN!**

I hope ma-enjoy nyo ito. Kindly DM **@BEGSHARK** if may concern/report.

━━━━━━━━━━━━━━━━━━
⚠️ **PLEASE STOP ABUSING THIS BOT**
🚫 Huwag mag-send ng **FAKE RECEIPT** — automatic **BAN**!

━━━━━━━━━━━━━━━━━━
💡 I started at **LOW PRICE**, so you guys can afford this.
🎁 You may have a **CHANCE TO GET PALDO ACCOUNT**!

━━━━━━━━━━━━━━━━━━
📢 **Join our channels:**
"""


BUY_TOKENS_MESSAGE = """
💳 **HELLO, INTERESTED TO BUY TOKENS?**

⚠️ This is **MANUAL ACCEPT**, so please:

📩 **DM @BEGSHARK** for approval
**OR** DM ZZEY **BEFORE** sending the money

━━━━━━━━━━━━━━━━━━
💰 **Token Prices:**
• 1 Token = ₱2
• 5 Tokens = ₱10
• 10 Tokens = ₱20
• 25 Tokens = ₱50
• 50 Tokens = ₱100
• 100 Tokens = ₱200

━━━━━━━━━━━━━━━━━━
📱 **GCash Details:**
Number: `{gcash_number}`
Name: `{gcash_name}`

━━━━━━━━━━━━━━━━━━
Thank you for understanding! 🙏
"""


SUPPORT_MESSAGE = """
📞 **Support & Contact**

━━━━━━━━━━━━━━━━━━
👤 **Admin:** @BEGSHARK
📢 **Channel:** @yourchannel

━━━━━━━━━━━━━━━━━━
⚠️ **PAALALA:**
• Huwag mag-send ng fake receipt
• Manual ang approval ng tokens
• DM muna bago mag-send ng pera

⏰ **Response time:** 1-24 hours
"""