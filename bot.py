async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    user_id = update.effective_user.id

    # 👉 LỆNH MENU (Hiển thị danh sách lệnh)
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

    # 👉 LỆNH DỊCH (Bắt đầu bằng dấu "/")
    if user_input.startswith("/"):
        text_to_translate = user_input[1:]  # Bỏ dấu "/" đầu
        messages = [
            {"role": "system", "content": "Translate this into natural Chinese or Vietnamese, based on input:"},
            {"role": "user", "content": text_to_translate}
        ]
    else:
        # 👉 Trả lời theo ngữ cảnh đã lưu
        messages = get_user_history(user_id) + [{"role": "user", "content": user_input}]

    try:
        response = openai.ChatCompletion.create(model=MODEL, messages=messages)
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"Lỗi khi gọi OpenAI: {e}"

    await update.message.reply_text(reply)

    # 👉 Lưu vào trí nhớ nếu KHÔNG phải lệnh dịch
    if not user_input.startswith("/"):
        append_history(user_id, "user", user_input)
        append_history(user_id, "assistant", reply)
