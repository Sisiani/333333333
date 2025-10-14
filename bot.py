import logging
import os
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ---------------- CONFIG ----------------
# Put your token into environment variable TOKEN on Railway (recommended)
TOKEN = os.environ.get("TOKEN", "7976882338:AAEUBtxPwiT6OUPBvzkaxpFgYzmT0yzD6Ps")
# Numeric admin id
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7374971382"))
# Channel username or invite (with @ or without)
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@flamingofilm1")
# Channel link for join button
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/flamingofilm1")

USERS_FILE = "users.json"

# ---------------- LABELS ----------------
BTN_GET_VIDEO = "دریافت فیلم 🤤"
BTN_MEMBERS = "اعضای ربات"
BTN_BROADCAST = "ارسال همگانی"  # only admin will see
# ---------------- LOGGER ----------------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- storage helpers ----------------
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_user(user_id, username=""):
    users = load_users()
    key = str(user_id)
    if key not in users:
        users[key] = {"username": username, "started": True}
        save_users(users)

def count_users():
    users = load_users()
    return len(users.keys())

# ---------------- Handlers ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, username=user.username or "")
    # Build keyboard: main button + members. If admin, add broadcast row.
    keyboard = [
        [KeyboardButton(BTN_GET_VIDEO)],
        [KeyboardButton(BTN_MEMBERS)]
    ]
    if user.id == ADMIN_ID:
        keyboard.append([KeyboardButton(BTN_BROADCAST)])
    reply = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("سلام! برای دریافت فیلم روی دکمه زیر بزنید.", reply_markup=reply)
    # If admin, also send an inline hint
    if user.id == ADMIN_ID:
        await update.message.reply_text("شما ادمین هستید — می‌توانید از دکمه‌ی ارسال همگانی برای ارسال پیام استفاده کنید.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message is None or update.message.text is None:
        return
    text = update.message.text.strip()
    user = update.effective_user
    uid = user.id

    # Admin broadcast flow: set waiting state then send
    if text == BTN_BROADCAST and user.id == ADMIN_ID:
        context.user_data["waiting_broadcast"] = True
        await update.message.reply_text("لطفا متن پیام همگانی را ارسال کنید (متن را در همین چت وارد کنید).")
        return
    if user.id == ADMIN_ID and context.user_data.get("waiting_broadcast"):
        msg = text
        users = load_users()
        sent = 0
        for target in list(users.keys()):
            try:
                await context.bot.send_message(int(target), msg)
                sent += 1
            except Exception:
                pass
        context.user_data["waiting_broadcast"] = False
        await update.message.reply_text(f"پیام برای {sent} کاربر ارسال شد ✅")
        return

    # Members count
    if text == BTN_MEMBERS:
        cnt = count_users()
        await update.message.reply_text(f"تعداد افرادی که ربات را استارت کرده‌اند: {cnt} نفر")
        return

    # Get video flow
    if text == BTN_GET_VIDEO:
        # Send message explaining need to join + buttons (join channel link + check membership)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("عضویت در کانال", url=CHANNEL_LINK)],
            [InlineKeyboardButton("من عضو شدم — بررسی کن", callback_data="check_member")]
        ])
        await update.message.reply_text("برای دریافت فیلم باید در کانال عضو شوی. ابتدا با دکمه‌ی زیر به کانال بپیوندید.", reply_markup=kb)
        return

    # fallback
    await update.message.reply_text("متوجه نشدم. لطفاً از منوی اصلی استفاده کنید یا /start را بزنید.")

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()
    data = query.data

    if data == "check_member":
        user = query.from_user
        uid = user.id
        # Try to check membership. CHANNEL_USERNAME should be like "@NEURANAcademy" or numeric id.
        try:
            member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
            status = member.status  # creator, administrator, member, restricted, left, kicked
            if status in ("member", "creator", "administrator"):
                # user is a member -> send the "file coming" message
                await query.message.reply_text("تبریک! شما عضو کانال هستید — فایل تا دقایقی دیگر ارسال خواهد شد.")
                # Optionally: send the actual file here if you have one. For now we only notify.
            else:
                await query.message.reply_text("شما هنوز عضو کانال نیستید. لطفا ابتدا به کانال بپیوندید.")
        except Exception as e:
            # Common causes: bot isn't allowed to access channel or CHANNEL_USERNAME wrong
            logger.exception(e)
            await query.message.reply_text("خطا در بررسی عضویت. لطفا مطمئن شوید نام کانال در تنظیمات درست است و ربات در کانال اضافه شده است (ربات باید در کانال عضو یا ادمین باشد).")

# ---------------- MAIN ----------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_handler(CallbackQueryHandler(callback_query_handler))

    logger.info("Bot started")
    app.run_polling()

if __name__ == '__main__':
    main()
