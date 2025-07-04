import openai
import os
import json
import re
from telegram import Update, Message
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

# ========== Cấu hình hệ thống ==========
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MODEL = "gpt-3.5-turbo"

# ==== Đặt admin chủ bot ở đây (ID dạng chuỗi, username không có @) ====
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

# ========== Lệnh chính cho quản trị group ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    allowed_groups.add(update.effective_chat.id)
    save_all()
    await update.message.reply_text("✅ Bot đã được bật tại nhóm này\n✅ 本群已启用机器人")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return
    user = update.effective_user
    if not is_mod(user.id, user.username):
        await update.message.reply_text("🚫 Bạn không có quyền sử dụng lệnh này\n🚫 您没有权限使用此指令")
        return
    allowed_groups.discard(update.effective_chat.id)
    save_all()
    await update.message.reply_text("🛑 Bot đã dừng tại nhóm này\n🛑 本群已禁用机器人")

async def out(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_group(update):
        return
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
        "/pay – Hướng dẫn thanh toán – 支付说明\n"
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
        "- 更多说明请看 /menu"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ========== LỆNH THANH TOÁN ==========
async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "💸 THANH TOÁN – 支付方式\n"
        "Bạn có thể chọn 1 trong 2 hình thức dưới đây:\n"
        "您可以选择以下两种方式之一：\n"
        "1️⃣ Huione Pay\n"
        "‣ Quét QR hoặc chuyển đến số: +84 776728642\n"
        "‣ 使用 Huione Pay 扫码，或转到：+84 776728642\n"
        "2️⃣ Nạp USDT (TRC20)\n"
        "‣ Quét QR dưới đây hoặc gửi USDT tới địa chỉ:\n"
        "‣ 扫描下方二维码或向以下地址转账 USDT：\n"
        "‣ TNBGvQAfFn5Ais4acNss4Y4XAkQBa26hfG\n"
        "‣ TNBGvQAfFn5Ais4acNss4Y4XAkQBa26hfG\n"
        "———————————————\n"
        "💬 LƯU Ý QUAN TRỌNG:\n"
        "💬 重要提醒：\n"
        "• Sau khi thanh toán, vui lòng gửi bill chuyển khoản thành công, ảnh rõ nét, không cắt góc, đầy đủ thông tin vào nhóm hoặc cho admin kiểm tra.\n"
        "• 转账后请发送付款截图（清晰、无缺角、所有信息完整）到群里或发给管理员确认。\n"
        "• Không để nội dung chuyển khoản.\n"
        "• 不要填写任何转账备注内容。\n"
        "• Chuyển đúng và đủ số tiền theo giá trị gói bot bạn muốn mua.\n"
        "• 请按所购套餐足额转账。\n"
        "• Bên mình KHÔNG có chính sách thối lại tiền nếu chuyển dư hoặc nhầm.\n"
        "• 如有多余金额或转错金额，本方不退款。\n"
    )
    try:
        with open("huione_qr.png", "rb") as qr_huione, open("trc20_qr.png", "rb") as qr_trc20:
            await update.message.reply_text(msg)
            await update.message.reply_photo(photo=qr_huione, caption="Huione Pay QR – Mã thanh toán | 收款码")
            await update.message.reply_photo(photo=qr_trc20, caption="USDT (TRC20) QR – Địa chỉ nạp | 充值地址")
    except Exception as e:
        await update.message.reply_text(msg + "\n\n⚠️ Không tìm thấy file mã QR thanh toán, liên hệ admin để nhận mã!")

# ========== LỆNH ADMIN/MOD (quản lý mod trong private) ==========
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

    if text.strip().lower().startswith("stop//"):
        if not is_admin(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền dùng auto dịch\n🚫 您没有权限使用自动翻译", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_translate", False)
        await msg.reply_text("🛑 Đã tắt chế độ tự động dịch!\n🛑 已关闭自动翻译模式", reply_to_message_id=msg.message_id)
        return
    if text.strip().lower().startswith("stop@@"):
        if not is_admin(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền dùng auto hỏi đáp\n🚫 您没有权限使用自动对话", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_chat", False)
        await msg.reply_text("🛑 Đã tắt chế độ auto hỏi đáp!\n🛑 已关闭自动对话模式", reply_to_message_id=msg.message_id)
        return

    if text.strip().startswith("//"):
        if not is_admin(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền bật auto dịch\n🚫 您没有权限开启自动翻译", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_translate", True)
        await msg.reply_text("✅ Đã bật chế độ tự động dịch!\n✅ 已开启自动翻译模式", reply_to_message_id=msg.message_id)
        return
    if text.strip().startswith("@@"):
        if not is_admin(user.id, user.username):
            await msg.reply_text("🚫 Bạn không có quyền bật auto hỏi đáp\n🚫 您没有权限开启自动对话", reply_to_message_id=msg.message_id)
            return
        set_auto_mode(chat.id, "auto_chat", True)
        await msg.reply_text("✅ Đã bật chế độ auto hỏi đáp!\n✅ 已开启自动对话模式", reply_to_message_id=msg.message_id)
        return

    if text.strip().startswith("/"):
        content = text.strip()[1:].strip()
        if not content or is_trivial(content):
            return
        await translate_and_reply(update, context, content)
        return

    if text.strip().startswith("@"):
        content = text.strip()[1:].strip()
        if not content or is_trivial(content):
            return
        await chat_gpt_and_reply(update, context, content)
        return

    if get_auto_mode(chat.id, "auto_translate"):
        if is_trivial(text):
            return
        await translate_and_reply(update, context, text)
        return
    if get_auto_mode(chat.id, "auto_chat"):
        if is_trivial(text):
            return
        await chat_gpt_and_reply(update, context, text)
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

# ========== Main ==========
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("out", out))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, handle_group_message))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_private))
    app.run_polling()

if __name__ == "__main__":
    main()
