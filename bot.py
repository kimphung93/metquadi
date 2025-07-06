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
from datetime import datetime, timedelta
import asyncio

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
notices = load_json("notices.json", {})

def save_all():
    save_json("memory.json", user_histories)
    save_json("auto_mode.json", auto_mode)
    save_json("active_groups.json", list(allowed_groups))
    save_json("mods.json", list(mods))
    save_json("notices.json", notices)

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
    return bool(re.fullmatch(r"[ .!?,:;…/\\\\|()\\[\\]\"'@#%^&*0-9\\-_=+~`♥️❤️👍😂😁🤔🥲😭🙂😉😅😆😇👀🌹💯⭐️🔥🙏🍀🍻🍺🍵☕️]*", text)) or \
        text.lower() in {"ok", "yes", "no", "thanks", "thx", "vâng", "ừ", "ừm", "uh", "dạ", "được", "hihi", "haha"}

def detect_lang(text):
    han_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if han_count >= 2:
        return "zh"
    return "vi"

# ========== Lệnh quản trị group ==========
async def on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền bật bot\n🚫 您没有权限启用机器人", reply_to_message_id=update.message.message_id)
        return
    allowed_groups.add(update.effective_chat.id)
    save_all()
    await update.message.reply_text("✅ Bot đã được bật tại nhóm này\n✅ 本群已启用机器人", reply_to_message_id=update.message.message_id)

async def off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền tắt bot\n🚫 您没有权限禁用机器人", reply_to_message_id=update.message.message_id)
        return
    allowed_groups.discard(update.effective_chat.id)
    save_all()
    await update.message.reply_text("🛑 Bot đã dừng tại nhóm này\n🛑 本群已禁用机器人", reply_to_message_id=update.message.message_id)

async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令", reply_to_message_id=update.message.message_id)
        return
    await update.message.reply_text("👋 Tạm biệt\n👋 再见", reply_to_message_id=update.message.message_id)
    await context.bot.leave_chat(update.effective_chat.id)

async def delldata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền xoá dữ liệu bot\n🚫 您没有权限清除机器人记忆", reply_to_message_id=update.message.message_id)
        return
    reset_history(update.effective_chat.id)
    await update.message.reply_text("🧹 Đã xoá lịch sử ghi nhớ của bot trong nhóm này\n🧹 已清除本群组的聊天记录", reply_to_message_id=update.message.message_id)

async def getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    title = update.effective_chat.title or "(Không có tiêu đề)"
    await update.message.reply_text(f"📌 ID nhóm: `{chat_id}`\n📘 Tên nhóm: {title}\n📌 群组ID：`{chat_id}`\n📘 群名称：{title}", parse_mode="Markdown")

# ========== Thông báo ==========
async def thongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_mod(user.id, user.username): return
    text = update.message.text
    m = re.match(r"^/thongbao (\d{2}:\d{2}) (.+)", text)
    if not m:
        await update.message.reply_text("Cú pháp: /thongbao [HH:MM] [nội dung]\n语法: /通知 [HH:MM] [内容]")
        return
    time_str, content = m.groups()
    group_id = str(update.effective_chat.id)
    notices[group_id] = {"time": time_str, "content": content}
    save_json("notices.json", notices)
    await update.message.reply_text(f"✅ Đã đặt thông báo lúc {time_str} cho nhóm này!\n✅ 已设置本群{time_str}的定时通知！")

async def xoathongbao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_mod(user.id, user.username): return
    group_id = str(update.effective_chat.id)
    if group_id in notices:
        del notices[group_id]
        save_json("notices.json", notices)
        await update.message.reply_text("🧹 Đã xoá thông báo nhóm này\n🧹 已清除本群定时通知")
    else:
        await update.message.reply_text("Nhóm này chưa đặt thông báo nào!\n本群还没有定时通知")

# ========== Gửi thông báo theo giờ ==========
async def scheduler(app):
    while True:
        now = datetime.now().strftime("%H:%M")
        for group_id, notice in notices.items():
            if notice["time"] == now:
                try:
                    await app.bot.send_message(
                        chat_id=int(group_id),
                        text=f"⏰ THÔNG BÁO / 通知：\n{notice['content']}"
                    )
                except: pass
        await asyncio.sleep(60)

# ========== MENU ==========
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    mod = is_mod(user.id, user.username)
    menu = [
        "📋 **HƯỚNG DẪN SỬ DỤNG BOT** – 机器人使用说明",
        "/fy – Dịch 1 lần – 翻译一次",
        "/fyon – Bật auto dịch – 开启自动翻译 (mod/admin)",
        "/fyoff – Dừng auto dịch – 关闭自动翻译 (mod/admin)",
        "/AI – AI trả lời 1 lần – AI问答一次",
        "/AIon – Auto AI trả lời – 自动问答 (mod/admin)",
        "/AIoff – Ngưng auto AI trả lời – 关闭自动问答 (mod/admin)",
        "/cskh – Hỗ trợ chuyên ngành – 专业客服一次",
        "/cskhon – Auto chuyên ngành – 自动专业客服 (mod/admin)",
        "/cskhoff – Ngưng auto chuyên ngành – 关闭自动专业客服 (mod/admin)",
        "/on – Bật bot tại nhóm này – 启用机器人 (mod/admin)",
        "/off – Tắt bot tại nhóm này – 禁用机器人 (mod/admin)",
        "/out – Bot rời nhóm – 机器人退出群 (mod/admin)",
        "/delldata – Xoá ghi nhớ nhóm – 清除本群聊天记录 (mod/admin)",
        "/thongbao [HH:MM] [nội dung] – Đặt thông báo – 设置定时通知 (mod/admin)",
        "/xoathongbao – Xoá thông báo – 取消通知 (mod/admin)",
        "/getid – Lấy ID nhóm – 获取群组ID"
    ]
    await update.message.reply_text("\n".join(menu), parse_mode="Markdown")

# ========== ADMIN/MOD Quản lý mod (chỉ riêng cho admin trong private) ==========
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
            await msg.reply_text("❌ Không thể thêm admin làm mod!\n❌ 不能把管理员加入MOD列表！")
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

    # Dịch 1 lần
    if text.strip().startswith("/fy "):
        content = text.strip()[4:].strip()
        if not content or is_trivial(content): return
        await translate_and_reply(update, context, content)
        return

    # Auto dịch
    if text.strip().startswith("/fyon"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Không có quyền bật auto dịch\n🚫 无权限开启自动翻译", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_translate", True)
        await msg.reply_text("✅ Đã bật auto dịch\n✅ 已开启自动翻译", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("/fyoff"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Không có quyền tắt auto dịch\n🚫 无权限关闭自动翻译", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_translate", False)
        await msg.reply_text("🛑 Đã tắt auto dịch\n🛑 已关闭自动翻译", reply_to_message_id=msg.message_id)
        return

    # AI 1 lần
    if text.strip().startswith("/AI "):
        content = text.strip()[4:].strip()
        if not content or is_trivial(content): return
        await chat_gpt_and_reply(update, context, content)
        return

    # Auto AI
    if text.strip().startswith("/AIon"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Không có quyền bật auto AI\n🚫 无权限开启自动AI", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_ai", True)
        await msg.reply_text("✅ Đã bật auto AI\n✅ 已开启自动AI", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("/AIoff"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Không có quyền tắt auto AI\n🚫 无权限关闭自动AI", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_ai", False)
        await msg.reply_text("🛑 Đã tắt auto AI\n🛑 已关闭自动AI", reply_to_message_id=msg.message_id)
        return

    # CSKH 1 lần
    if text.strip().startswith("/cskh "):
        content = text.strip()[6:].strip()
        if not content or is_trivial(content): return
        await cskh_reply(update, context, content)
        return

    # Auto CSKH
    if text.strip().startswith("/cskhon"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Không có quyền bật auto CSKH\n🚫 无权限开启自动客服", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_cskh", True)
        await msg.reply_text("✅ Đã bật auto CSKH\n✅ 已开启自动客服", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("/cskhoff"):
        if not is_mod(user.id, user.username):
            await msg.reply_text("🚫 Không có quyền tắt auto CSKH\n🚫 无权限关闭自动客服", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_cskh", False)
        await msg.reply_text("🛑 Đã tắt auto CSKH\n🛑 已关闭自动客服", reply_to_message_id=msg.message_id)
        return

    # Các lệnh khác
    if text.strip().startswith("/delldata"):
        await delldata(update, context)
        return

    if text.strip().startswith("/thongbao"):
        await thongbao(update, context)
        return

    if text.strip().startswith("/xoathongbao"):
        await xoathongbao(update, context)
        return

    if text.strip().startswith("/getid"):
        await getid(update, context)
        return

    if text.strip().startswith("/menu"):
        await menu(update, context)
        return

    if text.strip().startswith("/on"):
        await on(update, context)
        return

    if text.strip().startswith("/off"):
        await off(update, context)
        return

    if text.strip().startswith("/out"):
        await out(update, context)
        return

    # --- AUTO dịch ---
    if get_auto_mode(chat.id, "auto_translate"):
        if is_trivial(text): return
        await translate_and_reply(update, context, text)
        return

    # --- AUTO AI ---
    if get_auto_mode(chat.id, "auto_ai"):
        if is_trivial(text): return
        await chat_gpt_and_reply(update, context, text)
        return

    # --- AUTO CSKH ---
    if get_auto_mode(chat.id, "auto_cskh"):
        if is_trivial(text): return
        await cskh_reply(update, context, text)
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
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("getid", getid))
    app.add_handler(CommandHandler("delldata", delldata))
    app.add_handler(CommandHandler("on", on))
    app.add_handler(CommandHandler("off", off))
    app.add_handler(CommandHandler("out", out))
    app.add_handler(CommandHandler("thongbao", thongbao))
    app.add_handler(CommandHandler("xoathongbao", xoathongbao))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private))

    # Scheduler
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(app))

    app.run_polling()

if __name__ == "__main__":
    main()
