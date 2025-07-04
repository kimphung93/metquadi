import openai
import os
import json
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# === Thiết lập thông số & biến môi trường ===
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL = "gpt-3.5-turbo"

user_histories = {}

# === Quản lý bộ nhớ hội thoại ===
def load_memory():
    global user_histories
    if os.path.exists("memory.json"):
        with open("memory.json", "r", encoding="utf-8") as f:
            user_histories = json.load(f)
    else:
        user_histories = {}

def save_memory():
    with open("memory.json", "w", encoding="utf-8") as f:
        json.dump(user_histories, f, ensure_ascii=False, indent=2)

def get_user_history(user_id):
    return user_histories.get(str(user_id), [])

def append_history(user_id, role, content):
    uid = str(user_id)
    if uid not in user_histories:
        user_histories[uid] = []
    user_histories[uid].append({"role": role, "content": content})
    save_memory()

def reset_history(user_id):
    uid = str(user_id)
    if uid in user_histories:
        user_histories[uid] = []
        save_memory()

# === Các lệnh handler ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🤖 Xin chào! Tôi là bot hỗ trợ tiếng Việt & 中文.\n"
        "📖 Hãy gửi tin nhắn hoặc sử dụng /menu để xem chức năng.\n"
        "——\n"
        "🤖 你好！我是支持越南语和中文的机器人。\n"
        "📖 发送消息或输入 /menu 查看功能。"
    )
    await update.message.reply_text(msg)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📋 **DANH SÁCH LỆNH** – 指令列表\n"
        "/start - Bắt đầu sử dụng bot – 启动机器人\n"
        "/menu - Hiển thị menu chức năng – 显示功能菜单\n"
        "/translate <văn bản> - Dịch Việt/Trung – 翻译文本（越南语/中文）\n"
        "/reset - Xóa trí nhớ hội thoại – 清除对话记忆\n"
        "\nChỉ cần gửi câu hỏi, tôi sẽ trả lời tự động bằng AI!\n"
        "——\n"
        "直接发送问题，我会用AI自动回复！"
    )
    await update.message.reply_text(msg)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_history(update.effective_user.id)
    msg = "✅ Đã xóa toàn bộ lịch sử hội thoại!\n✅ 已清除所有对话记录！"
    await update.message.reply_text(msg)

async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "❗ Vui lòng nhập nội dung cần dịch sau lệnh /translate\n"
            "❗ 请在 /translate 后输入需要翻译的内容"
        )
        return
    text_to_translate = " ".join(args)
    messages = [
        {"role": "system", "content": "Translate this into natural Chinese or Vietnamese, based on input:"},
        {"role": "user", "content": text_to_translate}
    ]
    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}\n调用 OpenAI 时出错：{e}"
    await update.message.reply_text(reply)

# === Xử lý tin nhắn thường ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    user_id = update.effective_user.id

    # Nếu là lệnh không hợp lệ
    if user_input.startswith("/") and not user_input.startswith("/translate"):
        await update.message.reply_text(
            "❗ Lệnh không hợp lệ hoặc chưa hỗ trợ.\n"
            "❗ 指令无效或尚未支持。"
        )
        return

    # Lấy lịch sử, gửi tới OpenAI
    messages = get_user_history(user_id) + [{"role": "user", "content": user_input}]
    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}\n调用 OpenAI 时出错：{e}"

    await update.message.reply_text(reply)
    append_history(user_id, "user", user_input)
    append_history(user_id, "assistant", reply)

# === Khởi động bot ===
def main():
    load_memory()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("translate", translate))
    # Tin nhắn thường (không phải lệnh)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Lệnh không hợp lệ vẫn đi qua handle_message
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
