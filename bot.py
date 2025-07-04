
import os
import json
import openai
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

openai.api_key = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
HISTORY_FILE = "memory.json"
memory = {}

def load_memory():
    global memory
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            memory = json.load(f)

def save_memory():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def get_user_history(user_id):
    return memory.get(str(user_id), [])

def append_history(user_id, role, content):
    uid = str(user_id)
    if uid not in memory:
        memory[uid] = []
    memory[uid].append({"role": role, "content": content})
    if len(memory[uid]) > 20:
        memory[uid] = memory[uid][-20:]
    save_memory()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào bạn! Tôi là bot ChatGPT hỗ trợ dịch ngữ cảnh. Gõ gì đó hoặc dùng / để dịch.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    user_id = update.effective_user.id

    # Nếu là lệnh dịch (bắt đầu bằng /)
    if user_input.startswith("/"):
        text_to_translate = user_input[1:]
        messages = [{"role": "system", "content": "Translate this into natural Chinese or Vietnamese, based on input:"},
                    {"role": "user", "content": text_to_translate}]
    else:
        # Trả lời theo ngữ cảnh đã ghi nhớ
        messages = get_user_history(user_id) + [{"role": "user", "content": user_input}]

    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}"

    await update.message.reply_text(reply)

    # Ghi nhớ lịch sử nếu không phải dịch
    if not user_input.startswith("/"):
        append_history(user_id, "user", user_input)
        append_history(user_id, "assistant", reply)

def main():
    load_memory()
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
