import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

user_histories = {}

def load_memory():
    global user_histories
    if os.path.exists("memory.json"):
        with open("memory.json", "r", encoding="utf-8") as f:
            user_histories = json.load(f)
    else:
        user_histories = {}

def get_user_history(user_id):
    return user_histories.get(str(user_id), [])

def append_history(user_id, role, content):
    uid = str(user_id)
    if uid not in user_histories:
        user_histories[uid] = []
    user_histories[uid].append({"role": role, "content": content})
    with open("memory.json", "w", encoding="utf-8") as f:
        json.dump(user_histories, f, ensure_ascii=False, indent=2)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    user_id = update.effective_user.id

    if user_input.strip() == "/menu":
        await update.message.reply_text("""
 📋 DANH SÁCH LỆNH – 指令列表
/start - Bắt đầu sử dụng bot – 启动机器人
/stop - Dừng bot – 停止机器人
/menu - Hiển thị menu chức năng – 显示功能菜单
/translate - Dịch văn bản (Việt - Trung) – 翻译文本（越南语 - 中文）
/reset - Xoá toàn bộ trí nhớ hội thoại – 清除所有对话记忆
""")
        return

    if user_input.startswith("/"):
        text_to_translate = user_input[1:]
        messages = [
            {"role": "system", "content": "Translate this into natural Chinese or Vietnamese, based on input:"},
            {"role": "user", "content": text_to_translate}
        ]
    else:
        messages = get_user_history(user_id) + [{"role": "user", "content": user_input}]

    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}"

    await update.message.reply_text(reply)

    if not user_input.startswith("/"):
        append_history(user_id, "user", user_input)
        append_history(user_id, "assistant", reply)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tôi đây（在的）.")

def main():
    load_memory()
    app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
    
