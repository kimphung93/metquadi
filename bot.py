import openai
import os
import json
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# ======= THIẾT LẬP ===========
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL = "gpt-3.5-turbo"

# ======= QUẢN LÝ FILE =========
def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ======= KHỞI TẠO =========
user_histories = load_json("memory.json", {})
auto_mode = load_json("auto_mode.json", {})        # {group_id: {"auto_translate": True/False, ...}}
allowed_groups = set(load_json("active_groups.json", []))   # group_id đã bật bot
mods = set(str(i) for i in load_json("mods.json", []))      # user_id có quyền mod

def save_all():
    save_json("memory.json", user_histories)
    save_json("auto_mode.json", auto_mode)
    save_json("active_groups.json", list(allowed_groups))
    save_json("mods.json", list(mods))

# ======= HÀM TIỆN ÍCH =========
def is_group(update: Update):
    return update.effective_chat and update.effective_chat.type in ["group", "supergroup"]

def is_admin_or_mod(user_id):
    return str(user_id) in mods

def get_group_history(chat_id):
    return user_histories.get(str(chat_id), [])

def append_history(chat_id, role, content):
    cid = str(chat_id)
    if cid not in user_histories:
        user_histories[cid] = []
    user_histories[cid].append({"role": role, "content": content})
    save_json("memory.json", user_histories)

def reset_history(chat_id):
    cid = str(chat_id)
    if cid in user_histories:
        user_histories[cid] = []
        save_json("memory.json", user_histories)

def set_auto_mode(chat_id, mode, value):
    cid = str(chat_id)
    if cid not in auto_mode:
        auto_mode[cid] = {}
    auto_mode[cid][mode] = value
    save_json("auto_mode.json", auto_mode)

def get_auto_mode(chat_id, mode):
    cid = str(chat_id)
    return auto_mode.get(cid, {}).get(mode, False)

def is_trivial(text):
    """Kiểm tra tin nhắn chỉ là emoji, ký hiệu, hoặc ai cũng hiểu, không cần dịch."""
    text = text.strip()
    if not text: return True
    # Toàn ký hiệu hoặc emoji hoặc các từ phổ thông
    return bool(re.fullmatch(r"[ .!?,:;…/\\\\|()\\[\\]\"'@#%^&*0-9\\-_=+~`♥️❤️👍😂😁🤔🥲😭🙂😉😅😆😇👀🌹💯⭐️🔥🙏🍀🍻🍺🍵☕️]*", text)) \
        or text.lower() in {"ok", "yes", "no", "thanks", "thx", "vâng", "ừ", "ừm", "uh", "dạ", "được", "hihi", "haha"}

# ======= COMMAND HANDLERS =======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user.id
    if not is_admin_or_mod(user):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    allowed_groups.add(update.effective_chat.id)
    save_all()
    await update.message.reply_text("✅ Bot đã được bật tại nhóm này\n✅ 本群已启用机器人")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user.id
    if not is_admin_or_mod(user):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    allowed_groups.discard(update.effective_chat.id)
    save_all()
    await update.message.reply_text("🛑 Bot đã dừng tại nhóm này\n🛑 本群已禁用机器人")

async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user.id
    if not is_admin_or_mod(user):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    await update.message.reply_text("👋 Tạm biệt\n👋 再见")
    await context.bot.leave_chat(update.effective_chat.id)

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
    "📋 **HƯỚNG DẪN SỬ DỤNG BOT** – 机器人使用说明\n\n"
    "/start – Bật bot tại nhóm này – 启用机器人\n"
    "/stop – Tắt bot tại nhóm này – 禁用机器人\n"
    "/out – Bot rời nhóm – 机器人退出群\n"
    "/menu – Hiển thị menu lệnh – 显示功能菜单\n"
    "\n"
    "▶️ **Ký hiệu điều khiển:**\n"
    "`/` – Dịch 1 lần – 翻译一次\n"
    "`//` – Tự động dịch – 自动翻译\n"
    "`stop//` – Dừng tự động dịch – 停止自动翻译\n"
    "`@` – Trò chuyện GPT – 与机器人对话\n"
    "`@@` – Tự động hỏi đáp – 自动对话\n"
    "`stop@@` – Dừng auto hỏi đáp – 停止自动对话\n"
    "\n"
    "**Ví dụ | 例子:**\n"
    "/ 你好！   (dịch câu này)\n"
    "//         (bật auto dịch)\n"
    "stop//     (tắt auto dịch)\n"
    "@ Lịch sử Việt Nam là gì?\n"
    "@@        (bật auto hỏi đáp)\n"
    "stop@@    (tắt auto hỏi đáp)\n"
    "\n"
    "- Chỉ admin/mod mới bật/tắt bot trong nhóm\n"
    "- Mỗi nhóm hoạt động độc lập\n"
    "- Bot KHÔNG trả lời trong chat riêng\n"
    "- Tin nhắn toàn emoji, ký hiệu, 'ok', ... sẽ bị bỏ qua không dịch!\n"
    "- Khi dịch, bot chỉ reply bản dịch ngay dưới tin nhắn gốc, không lặp lại văn bản gốc.\n"
    "- Đầy đủ hướng dẫn ở /menu.\n"
    "——\n"
    "- 只有群管理/版主可以启动/禁用机器人\n"
    "- 每个群独立运作\n"
    "- 机器人不在私聊回复\n"
    "- 全部是表情、符号、“ok”类消息将被自动忽略\n"
    "- 翻译时仅回复译文，不重复原文\n"
    "- 更多说明请看 /menu"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ======= HANDLE MESSAGES =======
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in allowed_groups:
        return  # Group chưa bật bot
    msg = update.message
    text = msg.text or ""
    user_id = update.effective_user.id
    chat_id = chat.id

    # ==== LỆNH STOP AUTO ====
    if text.strip().lower().startswith("stop//"):
        set_auto_mode(chat_id, "auto_translate", False)
        await msg.reply_text("🛑 Đã tắt chế độ tự động dịch!\n🛑 已关闭自动翻译模式")
        return
    if text.strip().lower().startswith("stop@@"):
        set_auto_mode(chat_id, "auto_chat", False)
        await msg.reply_text("🛑 Đã tắt chế độ auto hỏi đáp!\n🛑 已关闭自动对话模式")
        return

    # ==== LỆNH AUTO MODE ====
    if text.strip().startswith("//"):
        set_auto_mode(chat_id, "auto_translate", True)
        await msg.reply_text("✅ Đã bật chế độ tự động dịch!\n✅ 已开启自动翻译模式")
        return
    if text.strip().startswith("@@"):
        set_auto_mode(chat_id, "auto_chat", True)
        await msg.reply_text("✅ Đã bật chế độ auto hỏi đáp!\n✅ 已开启自动对话模式")
        return

    # ==== XỬ LÝ TIN NHẮN THEO LỆNH ĐẦU DÒNG ====
    # Dịch 1 lần
    if text.strip().startswith("/"):
        content = text.strip()[1:].strip()
        if not content or is_trivial(content):
            return
        await translate_and_reply(update, context, content)
        return

    # Hỏi đáp GPT 1 lần
    if text.strip().startswith("@"):
        content = text.strip()[1:].strip()
        if not content or is_trivial(content):
            return
        await chat_gpt_and_reply(update, context, content)
        return

    # ==== XỬ LÝ THEO AUTO MODE ====
    # AUTO DỊCH
    if get_auto_mode(chat_id, "auto_translate"):
        if is_trivial(text):
            return
        await translate_and_reply(update, context, text)
        return
    # AUTO HỎI ĐÁP
    if get_auto_mode(chat_id, "auto_chat"):
        if is_trivial(text):
            return
        await chat_gpt_and_reply(update, context, text)
        return

    # Nếu không thuộc bất cứ trường hợp nào trên -> bot im lặng
    return

# ======= REPLY LOGIC =======
async def translate_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, content):
    chat_id = update.effective_chat.id
    history = get_group_history(chat_id)
    # Giữ lịch sử ngữ cảnh
    messages = history[-6:] + [
        {"role": "system", "content": "Translate this into natural Chinese or Vietnamese, based on input."},
        {"role": "user", "content": content}
    ]
    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}\n调用 OpenAI 时出错：{e}"
    await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    append_history(chat_id, "user", content)
    append_history(chat_id, "assistant", reply)

async def chat_gpt_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, content):
    chat_id = update.effective_chat.id
    history = get_group_history(chat_id)
    messages = history[-8:] + [{"role": "user", "content": content}]
    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}\n调用 OpenAI 时出错：{e}"
    await update.message.reply_text(reply, reply_to_message_id=update.message.message_id)
    append_history(chat_id, "user", content)
    append_history(chat_id, "assistant", reply)

# ======= MAIN =========
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("out", out))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.run_polling()

if __name__ == "__main__":
    main()
