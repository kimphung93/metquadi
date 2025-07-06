import openai
import os
import json
import re
from telegram import (
    Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# ========== Cấu hình hệ thống ==========
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL = "gpt-3.5-turbo"

ADMIN_IDS = ["6902075720", "5195012187"]
ADMIN_USERNAMES = ["sunshine168888", "white9xinfo"]

def is_admin(user_id, username):
    uname = str(username).lstrip('@').lower() if username else ""
    return (str(user_id) in ADMIN_IDS) or (uname in [u.lower() for u in ADMIN_USERNAMES])

def is_mod(user_id, username):
    if is_admin(user_id, username):
        return True
    return str(username).lstrip('@').lower() in {u.lower().lstrip('@') for u in mods}

def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

user_histories = load_json("memory.json", {})
auto_mode = load_json("auto_mode.json", {})
allowed_groups = set(load_json("active_groups.json", []))
mods = set(load_json("mods.json", []))

def save_all():
    save_json("memory.json", user_histories)
    save_json("auto_mode.json", auto_mode)
    save_json("active_groups.json", list(allowed_groups))
    save_json("mods.json", list(mods))

def is_group(update: Update):
    return update.effective_chat and update.effective_chat.type in ["group", "supergroup"]

def is_private(update: Update):
    return update.effective_chat and update.effective_chat.type == "private"

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
    text = text.strip()
    if not text: return True
    return bool(re.fullmatch(r"[ .!?,:;…/\\\\|()\\[\\]\"'@#%^&*0-9\\-_=+~`♥️❤️👍😂😁🤔🥲😭🙂😉😅😆😇👀🌹💯⭐️🔥🙏🍀🍻🍺🍵☕️]*", text)) \
        or text.lower() in {"ok", "yes", "no", "thanks", "thx", "vâng", "ừ", "ừm", "uh", "dạ", "được", "hihi", "haha"}

def detect_lang(text):
    han_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if han_count >= 2:
        return "zh"
    return "vi"

# ========== Lệnh quản trị group ==========
async def onjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令", reply_to_message_id=update.message.message_id)
        return
    allowed_groups.add(update.effective_chat.id)
    save_all()
    await update.message.reply_text("✅ Bot đã được bật tại nhóm này\n✅ 本群已启用机器人", reply_to_message_id=update.message.message_id)

async def offjob(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令", reply_to_message_id=update.message.message_id)
        return
    allowed_groups.discard(update.effective_chat.id)
    save_all()
    await update.message.reply_text("🛑 Bot đã dừng tại nhóm này\n🛑 本群已禁用机器人", reply_to_message_id=update.message.message_id)

async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_admin(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令", reply_to_message_id=update.message.message_id)
        return
    await update.message.reply_text("👋 Tạm biệt\n👋 再见", reply_to_message_id=update.message.message_id)
    await context.bot.leave_chat(update.effective_chat.id)

# ========== InlineKeyboard auto menu (cho tất cả auto) ==========
async def automenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Bật auto dịch", callback_data="auto_on"),
         InlineKeyboardButton("Tắt auto dịch", callback_data="auto_off")],
        [InlineKeyboardButton("Bật auto AI", callback_data="ai_on"),
         InlineKeyboardButton("Tắt auto AI", callback_data="ai_off")],
        [InlineKeyboardButton("Bật auto CSKH", callback_data="cskh_on"),
         InlineKeyboardButton("Tắt auto CSKH", callback_data="cskh_off")],
    ]
    await update.message.reply_text(
        "🎛️ Chọn chức năng auto:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    chat_id = query.message.chat_id

    if data in {"auto_on", "auto_off", "ai_on", "ai_off", "cskh_on", "cskh_off"}:
        if not is_mod(user.id, user.username):
            await query.answer("🚫 Bạn không có quyền thực hiện chức năng này!", show_alert=True)
            return

    if data == "auto_on":
        set_auto_mode(chat_id, "auto_translate", True)
        await query.answer("✅ Đã bật auto dịch!", show_alert=True)
        await query.edit_message_text("Đã bật auto dịch trong nhóm này.")
    elif data == "auto_off":
        set_auto_mode(chat_id, "auto_translate", False)
        await query.answer("🛑 Đã tắt auto dịch!", show_alert=True)
        await query.edit_message_text("Đã tắt auto dịch trong nhóm này.")
    elif data == "ai_on":
        set_auto_mode(chat_id, "auto_ai", True)
        await query.answer("✅ Đã bật auto AI!", show_alert=True)
        await query.edit_message_text("Đã bật auto AI trong nhóm này.")
    elif data == "ai_off":
        set_auto_mode(chat_id, "auto_ai", False)
        await query.answer("🛑 Đã tắt auto AI!", show_alert=True)
        await query.edit_message_text("Đã tắt auto AI trong nhóm này.")
    elif data == "cskh_on":
        set_auto_mode(chat_id, "auto_cskh", True)
        await query.answer("✅ Đã bật auto CSKH!", show_alert=True)
        await query.edit_message_text("Đã bật auto CSKH trong nhóm này.")
    elif data == "cskh_off":
        set_auto_mode(chat_id, "auto_cskh", False)
        await query.answer("🛑 Đã tắt auto CSKH!", show_alert=True)
        await query.edit_message_text("Đã tắt auto CSKH trong nhóm này.")

# ========== MENU ==========
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mod = is_mod(user.id, user.username)
    menu = [
        "📋 **HƯỚNG DẪN SỬ DỤNG BOT** – 机器人使用说明\n",
        "/      – Dịch 1 lần – 翻译一次",
        "/;     – AI trả lời 1 lần – AI问答一次",
        "/-     – Hỗ trợ chuyên ngành 1 lần – 专业客服一次"
    ]
    if mod:
        menu += [
            "/auto   – Tự động dịch – 自动翻译",
            "/off    – Dừng auto dịch – 关闭自动翻译",
            "/;auto  – Auto AI trả lời – 自动问答",
            "/;off   – Ngưng auto AI trả lời – 关闭自动问答",
            "/-auto  – Auto chuyên ngành – 自动专业客服",
            "/-off   – Ngưng auto chuyên ngành – 关闭自动专业客服",
            "/onjob  – Bật bot tại nhóm này – 启用机器人",
            "/offjob – Tắt bot tại nhóm này – 禁用机器人",
            "/out    – Bot rời nhóm – 机器人退出群",
            "/automenu – Menu auto bằng nút – 自动菜单"
        ]
    msg = "\n".join(menu)
    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== ADMIN/MOD (quản lý mod trong private) ==========
async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.message
    user = update.effective_user
    username = (user.username or "").lstrip('@')
    if not is_admin(user.id, user.username):
        return

    text = (msg.text or "").strip()
    if not text: return
    match_add = re.match(r"^\+\s*@?(\w+)", text)
    if match_add:
        modname = match_add.group(1)
        modname = modname.lstrip('@')
        if modname.lower() in [u.lower() for u in ADMIN_USERNAMES]:
            await msg.reply_text(f"❌ Không thể thêm admin làm mod!\n❌ 不能把管理员加入MOD列表！")
            return
        if modname.lower() in {u.lower().lstrip('@') for u in mods}:
            await msg.reply_text(f"⚠️ @{modname} đã là mod!\n⚠️ @{modname} 已经是MOD了！")
            return
        mods.add(modname)
        save_json("mods.json", list(mods))
        await msg.reply_text(f"✅ Đã thêm @{modname} làm mod!\n✅ 已添加 @{modname} 成为MOD！")
        return
    match_remove = re.match(r"^-\s*@?(\w+)", text)
    if match_remove:
        modname = match_remove.group(1)
        modname = modname.lstrip('@')
        if modname.lower() not in {u.lower().lstrip('@') for u in mods}:
            await msg.reply_text(f"⚠️ @{modname} không phải mod!\n⚠️ @{modname} 不是MOD！")
            return
        mods.discard(modname)
        save_json("mods.json", list(mods))
        await msg.reply_text(f"✅ Đã xoá @{modname} khỏi mod!\n✅ 已从MOD列表移除 @{modname}！")
        return
    if text.lower() in {"mod", "mods", "danhsachmod", "dsmod"}:
        modlist = "\n".join(f"@{m}" for m in mods) or "Không có MOD nào.\n暂无MOD。"
        await msg.reply_text(f"Danh sách mod hiện tại:\n{modlist}\n\n当前MOD列表：\n{modlist}")
        return

# ========== Xử lý tin nhắn nhóm ==========
async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.id not in allowed_groups:
        return
    msg = update.message
    text = msg.text or ""
    user = update.effective_user

    # --- Lệnh auto dịch ---
    if text.strip().startswith("/auto"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền bật auto dịch\n🚫 您没有权限开启自动翻译", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_translate", True)
        await msg.reply_text("✅ Đã bật chế độ tự động dịch!\n✅ 已开启自动翻译模式", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("/off"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền tắt auto dịch\n🚫 您没有权限关闭自动翻译", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_translate", False)
        await msg.reply_text("🛑 Đã tắt chế độ tự động dịch!\n🛑 已关闭自动翻译模式", reply_to_message_id=msg.message_id)
        return

    # --- Lệnh auto AI ---
    if text.strip().startswith("/;auto"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền bật auto AI\n🚫 您没有权限开启自动问答", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_ai", True)
        await msg.reply_text("✅ Đã bật auto hỏi đáp!\n✅ 已开启自动问答模式", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("/;off"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền tắt auto AI\n🚫 您没有权限关闭自动问答", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_ai", False)
        await msg.reply_text("🛑 Đã tắt auto hỏi đáp!\n🛑 已关闭自动问答模式", reply_to_message_id=msg.message_id)
        return

    # --- Lệnh auto chuyên ngành (CSKH) ---
    if text.strip().startswith("/-auto"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền bật auto CSKH\n🚫 您没有权限开启自动客服", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_cskh", True)
        await msg.reply_text("✅ Đã bật auto hỗ trợ chuyên ngành!\n✅ 已开启自动专业客服", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("/-off"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền tắt auto CSKH\n🚫 您没有权限关闭自动客服", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_cskh", False)
        await msg.reply_text("🛑 Đã tắt auto hỗ trợ chuyên ngành!\n🛑 已关闭自动专业客服", reply_to_message_id=msg.message_id)
        return

    # --- Dịch 1 lần ---
    if text.strip().startswith("/") and not text.strip().startswith(("/auto", "/off", "/;auto", "/;off", "/-auto", "/-off", "/onjob", "/offjob", "/out", "/automenu")):
        content = text.strip()[1:].strip()
        if not content or is_trivial(content):
            return
        await translate_and_reply(update, context, content)
        return

    # --- AI trả lời 1 lần ---
    if text.strip().startswith("/;") and not text.strip().startswith("/;auto") and not text.strip().startswith("/;off"):
        content = text.strip()[2:].strip()
        if not content or is_trivial(content):
            return
        await chat_gpt_and_reply(update, context, content)
        return

    # --- CSKH chuyên ngành trả lời 1 lần ---
    if text.strip().startswith("/-") and not text.strip().startswith("/-auto") and not text.strip().startswith("/-off"):
        content = text.strip()[2:].strip()
        if not content or is_trivial(content):
            return
        await cskh_reply(update, context, content)
        return

    # --- AUTO dịch ---
    if get_auto_mode(chat.id, "auto_translate"):
        if is_trivial(text):
            return
        await translate_and_reply(update, context, text)
        return

    # --- AUTO AI ---
    if get_auto_mode(chat.id, "auto_ai"):
        if is_trivial(text):
            return
        await chat_gpt_and_reply(update, context, text)
        return

    # --- AUTO CSKH ---
    if get_auto_mode(chat.id, "auto_cskh"):
        if is_trivial(text):
            return
        await cskh_reply(update, context, text)
        return

    return

# ========== Tương tác OpenAI ==========
async def translate_and_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, content):
    chat_id = update.effective_chat.id
    history = get_group_history(chat_id)
    lang = detect_lang(content)
    if lang == "vi":
        prompt = "Chỉ dịch sang tiếng Trung giản thể. Tuyệt đối KHÔNG lặp lại văn bản gốc, không chú thích, không giải thích."
    else:
        prompt = "Chỉ dịch sang tiếng Việt. Tuyệt đối KHÔNG lặp lại văn bản gốc, không chú thích, không giải thích."
    messages = history[-6:] + [
        {"role": "system", "content": prompt},
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

async def cskh_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, content):
    chat_id = update.effective_chat.id
    prompt = "Bạn là chuyên viên CSKH nhà cái, chỉ trả lời đúng quy trình/nghiệp vụ được quy định, không tự ý sáng tạo."
    messages = get_group_history(chat_id)[-8:] + [
        {"role": "system", "content": prompt},
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

# ========== Main ==========
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("onjob", onjob))
    app.add_handler(CommandHandler("offjob", offjob))
    app.add_handler(CommandHandler("out", out))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("automenu", automenu))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private))
    app.run_polling()

if __name__ == "__main__":
    main()
