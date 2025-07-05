import openai
import os
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, CallbackQueryHandler, filters
)

# ================== CONFIG ===============
openai.api_key = os.getenv("OPENAI_API_KEY", "sk-xxxxxx")   # Đổi key nếu cần
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "123:xxx") # Đổi token nếu cần
MODEL = "gpt-3.5-turbo"
ADMIN_ID = 6902075720
ADMIN_USERNAME = "sunshine168888"

# ---- Thông tin thanh toán
USDT_ADDR = "TNBGvQAfFn5Ais4acNss4Y4XAkQBa26hfG"
HUIONE_QR_PATH = "13bf0fbf-33de-4a7d-97b8-559f1af109f0.png"
USDT_QR_PATH = "de39a519-30b0-4346-acba-aa24f8fc6be5.png"
GIA_NGAY = "5$"
GIA_TUAN = "15$"
GIA_THANG = "35$"
FORWARD_PRIVATE_PAYMENT = True  # True: forward hóa đơn về admin inbox
MAX_SPAM = 3  # Số lần spam trước khi cảnh báo

# =========================================

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
paid_groups = load_json("paid_groups.json", {})
spam_tracker = load_json("spam_tracker.json", {})  # {str(user_id): count}

def save_all():
    save_json("memory.json", user_histories)
    save_json("auto_mode.json", auto_mode)
    save_json("active_groups.json", list(allowed_groups))
    save_json("mods.json", list(mods))
    save_json("paid_groups.json", paid_groups)
    save_json("spam_tracker.json", spam_tracker)

def is_group(update: Update):
    return update.effective_chat and update.effective_chat.type in ["group", "supergroup"]

def is_private(update: Update):
    return update.effective_chat and update.effective_chat.type == "private"

def is_admin(user_id, username):
    return (str(user_id) == str(ADMIN_ID)) or (str(username).lstrip('@').lower() == ADMIN_USERNAME.lower())

def is_mod(user_id, username):
    if is_admin(user_id, username):
        return True
    return str(username).lstrip('@').lower() in {u.lower().lstrip('@') for u in mods}

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

def group_has_paid(chat_id):
    gid = str(chat_id)
    info = paid_groups.get(gid)
    if not info: return False
    from datetime import datetime
    try:
        expire = info.get("expire")
        if not expire: return False
        dt_expire = datetime.strptime(expire, "%Y-%m-%d")
        return dt_expire.date() >= datetime.now().date()
    except Exception:
        return False

def build_license_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Đăng ký bản quyền", callback_data="reg_license")],
        [InlineKeyboardButton("Tôi chưa có nhu cầu", callback_data="no_need")]
    ])

def build_package_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Gói ngày ({GIA_NGAY})", callback_data="pkg_ngay")],
        [InlineKeyboardButton(f"Gói tuần ({GIA_TUAN})", callback_data="pkg_tuan")],
        [InlineKeyboardButton(f"Gói tháng ({GIA_THANG})", callback_data="pkg_thang")],
    ])

async def handle_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg: Message = update.message
    user = update.effective_user
    username = (user.username or "").lstrip('@')
    if is_admin(user.id, user.username):
        # Xử lý lệnh mod như cũ
        text = (msg.text or "").strip()
        if not text: return
        match_add = re.match(r"^\+\s*@?(\w+)", text)
    if match_add:
            modname = match_add.group(1)
            modname = modname.lstrip('@')
    if modname.lower() == ADMIN_USERNAME.lower():
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
    else:
        # Hiện menu đăng ký bản quyền cho user thường
        await msg.reply_text(
            "🔒 Đăng ký bản quyền sử dụng bot để mở khoá toàn bộ chức năng!\n\n"
            "Nhấn vào nút bên dưới để đăng ký:",
            reply_markup=build_license_keyboard()
        )

async def handle_license_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    if data == "reg_license":
        await query.message.reply_text(
            "Vui lòng chọn gói dịch vụ bạn muốn đăng ký:",
            reply_markup=build_package_keyboard()
        )
    elif data == "pkg_ngay":
        await send_payment_info(query, "ngày", GIA_NGAY, context)
    elif data == "pkg_tuan":
        await send_payment_info(query, "tuần", GIA_TUAN, context)
    elif data == "pkg_thang":
        await send_payment_info(query, "tháng", GIA_THANG, context)
    elif data == "no_need":
        await query.message.reply_text("Cảm ơn bạn đã quan tâm! Khi nào cần có thể vào /menu để đăng ký bất cứ lúc nào.")

async def send_payment_info(query, goi, gia, context):
    text = (
        f"**Đăng ký gói {goi}**\n"
        f"- Giá: {gia}\n\n"
        f"Vui lòng gửi các thông tin sau cho bot này:\n"
        f"1. Username Telegram: (ví dụ @tenban)\n"
        f"2. ID Telegram: lấy tại @EskoIDBot\n"
        f"3. Gửi ảnh hóa đơn chuyển khoản (USDT hoặc Huione)\n\n"
        f"**Thông tin chuyển khoản:**\n"
        f"- USDT (TRC20): `{USDT_ADDR}`\n"
        f"- Hoặc dùng mã QR bên dưới\n\n"
        f"**Lưu ý:**\n"
        f"- Chuyển đúng số tiền, không hoàn tiền nếu chuyển dư\n"
        f"- Không ghi nội dung khi chuyển khoản\n"
    )
    await query.message.reply_text(text, parse_mode="Markdown")
    # Gửi QR code
    try:
        with open(HUIONE_QR_PATH, "rb") as f:
            await query.message.reply_photo(photo=f, caption="QR Huione Pay")
    except Exception:
        await query.message.reply_text("Không gửi được ảnh QR Huione. Liên hệ admin để nhận mã QR.")
    try:
        with open(USDT_QR_PATH, "rb") as f:
            await query.message.reply_photo(photo=f, caption="QR USDT TRC20")
    except Exception:
        await query.message.reply_text("Không gửi được ảnh QR USDT. Liên hệ admin để nhận mã QR.")

async def handle_payment_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Khi user gửi ảnh hóa đơn (screenshot) ở chat riêng
    message = update.message
    user = message.from_user
    caption = f"KH đăng ký bản quyền:\nUsername: @{user.username}\nID: {user.id}\n"
    if message.caption:
        caption += f"Thông tin bổ sung: {message.caption}\n"
    caption += "Ảnh hóa đơn chuyển khoản bên dưới."
    if FORWARD_PRIVATE_PAYMENT:
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id, caption=caption)
    await message.reply_text("Đang xác nhận, vui lòng chờ admin kiểm tra!")

def anyone_is_mod_admin(members):
    """members là list dict chứa user_id, username, status"""
    for m in members:
    if is_mod(m.get("user_id"), m.get("username")):
            return True
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    allowed_groups.add(update.effective_chat.id)
    save_all()
    await update.message.reply_text("✅ Bot đã được bật tại nhóm này\n✅ 本群已启用机器人")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    allowed_groups.discard(update.effective_chat.id)
    save_all()
    await update.message.reply_text("🛑 Bot đã dừng tại nhóm này\n🛑 本群已禁用机器人")

async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update): return
    user = update.effective_user
    if not is_admin(user.id, user.username):
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
    "`//` – Tự động dịch – 自动翻译 (Chỉ admin!)\n"
    "`stop//` – Dừng tự động dịch – 停止自动翻译 (Chỉ admin!)\n"
    "`@` – Trò chuyện GPT – 与机器人对话\n"
    "`@@` – Tự động hỏi đáp – 自动对话 (Chỉ admin!)\n"
    "`stop@@` – Dừng auto hỏi đáp – 停止自动对话 (Chỉ admin!)\n"
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
    "- Bot KHÔNG trả lời trong chat riêng (ngoại trừ admin lệnh mod)\n"
    "- Tin nhắn toàn emoji, ký hiệu, 'ok', ... sẽ bị bỏ qua không dịch!\n"
    "- Khi dịch, bot chỉ reply bản dịch ngay dưới tin nhắn gốc, không lặp lại văn bản gốc.\n"
    "- Đầy đủ hướng dẫn ở /menu.\n"
    "——\n"
    "- 只有群管理/版主可以启动/禁用机器人\n"
    "- 每个群独立运作\n"
    "- 机器人不在私聊回复（除非管理员管理MOD）\n"
    "- 全部是表情、符号、“ok”类消息将被自动忽略\n"
    "- 翻译时仅回复译文，不重复原文\n"
    "- 更多说明请看 /menu",
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    # Thêm menu đăng ký bản quyền cho thành viên thường
    if is_private(update):
        await update.message.reply_text(
            "🔒 Đăng ký bản quyền sử dụng bot để mở khoá toàn bộ chức năng!\n\n"
            "Nhấn vào nút bên dưới để đăng ký:",
            reply_markup=build_license_keyboard()
        )

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    chat_id = chat.id
    msg = update.message
    user = update.effective_user
    is_paid = group_has_paid(chat_id)
    is_allowed = chat_id in allowed_groups
    has_mod = is_mod(user.id, user.username)
    if not (is_allowed or is_paid):
        # Kiểm tra số lần spam của user
        u_id = str(user.id)
        cnt = spam_tracker.get(u_id, 0) + 1
        spam_tracker[u_id] = cnt
        if cnt == MAX_SPAM:
            await msg.reply_text("Hiện bot chưa thể hỗ trợ bạn, vui lòng liên hệ @fanyi_aallive_bot", reply_to_message_id=msg.message_id)
        save_json("spam_tracker.json", spam_tracker)
        return
    # Đúng quyền rồi thì reset spam count
    if str(user.id) in spam_tracker:
        spam_tracker[str(user.id)] = 0
        save_json("spam_tracker.json", spam_tracker)
    text = msg.text or ""

    # Admin/mod hoặc nhóm trả phí mới dùng auto
    if
