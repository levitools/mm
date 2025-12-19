import os
import re
import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
)

# ================= CONFIG =================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # LẤY TOKEN TỪ ENV
PORT = int(os.environ.get("PORT", 10000))
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# ================= APP =================
flask_app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

# ================= DATA =================
user_data = {}

# ================= LOGIC CŨ (GIỮ NGUYÊN) =================
def parse_input(text):
    parts = text.split()
    date_match = re.search(r'(\d{1,2}/\d{1,2})', text)
    date = date_match.group(1) if date_match else ""

    dac_biet = super_tt = vip_tt = super_bt = tip_nv = da_ck = 0
    combined_text = " ".join(parts).lower()

    for key, var in [
        ("dacbiet", "dac_biet"),
        ("super", "super_tt"),
        ("vip", "vip_tt"),
        ("v500", "super_bt"),
    ]:
        m = re.search(rf'(\d+)\s*{key}', combined_text)
        if m:
            locals()[var] = int(m.group(1))

    for i, part in enumerate(parts):
        if "cknv" in part.lower() and i + 1 < len(parts):
            tip_nv = int(parts[i + 1]) * 1000
        if "dack" in part.lower() and i + 1 < len(parts):
            da_ck = int(parts[i + 1]) * 1000

    return {
        "date": date,
        "dac_biet": dac_biet,
        "super_tt": super_tt,
        "vip_tt": vip_tt,
        "super_bt": super_bt,
        "tip_nv": tip_nv,
        "da_ck": da_ck,
    }

def calculate_revenue(data):
    total_revenue = (
        data["dac_biet"] * 1700000
        + data["super_tt"] * 700000
        + data["vip_tt"] * 600000
        + data["super_bt"] * 500000
    )

    tien_goc = (
        data["dac_biet"] * 1100000
        + (data["super_tt"] + data["vip_tt"]) * 400000
        + data["super_bt"] * 500000
    )

    total_ve = sum(
        [data["dac_biet"], data["super_tt"], data["vip_tt"], data["super_bt"]]
    )

    return {
        "total_ve": total_ve,
        "total_revenue": total_revenue,
        "tien_goc": tien_goc,
        "tien_ngon_nv": total_revenue - tien_goc,
        "total_ve_tip": total_revenue + data["tip_nv"],
        "tien_mat": total_revenue + data["tip_nv"] - data["da_ck"],
    }

def format_currency(n):
    return f"{n:,.0f}".replace(",", ".")

def format_output(data, calc):
    return f"""Dạ anh Ba doanh thu Massage Royal An An ngày {data['date']} gồm:

Tổng {calc['total_ve']} vé = {format_currency(calc['total_revenue'])}đ
Tiền gốc: {format_currency(calc['tien_goc'])}đ
Tiền ngọn NV: {format_currency(calc['tien_ngon_nv'])}đ
Tip NV: {format_currency(data['tip_nv'])}đ
Tổng vé + tip: {format_currency(calc['total_ve_tip'])}đ
Đã CK: {format_currency(data['da_ck'])}đ
Còn lại tiền mặt: {format_currency(calc['tien_mat'])}đ
"""

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot Webhook đang hoạt động ✅")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = parse_input(update.message.text)
    calc = calculate_revenue(data)
    await update.message.reply_text(format_output(data, calc))

# ================= REGISTER =================
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ================= FLASK ROUTES =================
@flask_app.route("/")
def home():
    return "Bot is alive"

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "OK"

# ================= MAIN =================
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("❌ Chưa set BOT_TOKEN trong ENV")

    WEBHOOK_URL = f"https://YOUR-APP-NAME.onrender.com{WEBHOOK_PATH}"
    application.bot.set_webhook(WEBHOOK_URL)

    flask_app.run(host="0.0.0.0", port=PORT)
