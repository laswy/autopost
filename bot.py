#!/usr/bin/env python3
"""
AutoPost Telegram Bot
━━━━━━━━━━━━━━━━━━━━
Nhận lệnh từ Telegram, viết truyện bằng AI (NNA/NPV skill),
chuyển thành video TikTok rồi upload hoặc gửi về Telegram.

Lệnh:
  /start          — Hướng dẫn sử dụng
  /story <prompt> — Viết truyện NNA + tạo video
  /poem <prompt>  — Viết thơ NPV + tạo video
  /voices         — Danh sách giọng đọc
  /genres         — Danh sách thể loại
  /settings       — Xem / đổi cài đặt hiện tại
  /cancel         — Huỷ tác vụ đang chạy
"""

import asyncio
import logging
import os
import traceback
from functools import wraps

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    Update, BotCommand,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, ConversationHandler,
)

import config
from config import AI_PROVIDER
from skills.nna_writer import write_story, generate_hook, generate_caption
from skills.story_pipeline import run_pipeline
from skills.tiktok_upload import uploader

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── Conversation states ────────────────────────────────────────────────────────
WAIT_GENRE, WAIT_VOICE, WAIT_UPLOAD_CONFIRM = range(3)

GENRES = {
    "romance":      "💔 Tình cảm",
    "horror":       "👻 Kinh dị",
    "motivational": "🔥 Cảm hứng",
    "mystery":      "🔎 Bí ẩn",
    "general":      "📖 Tổng hợp",
}

VOICES = {
    "vi-VN-HoaiMyNeural":  "🇻🇳 Hoài My (nữ)",
    "vi-VN-NamMinhNeural": "🇻🇳 Nam Minh (nam)",
    "en-US-JennyNeural":   "🇺🇸 Jenny (nữ, EN)",
}

# ── Auth decorator ─────────────────────────────────────────────────────────────
def restricted(func):
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if config.ALLOWED_USER_IDS and uid not in config.ALLOWED_USER_IDS:
            await update.message.reply_text("⛔ Bạn không có quyền dùng bot này.")
            return
        return await func(update, ctx)
    return wrapper

# ── Helpers ────────────────────────────────────────────────────────────────────
def _genre_keyboard() -> InlineKeyboardMarkup:
    rows = []
    items = list(GENRES.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(v, callback_data=f"genre:{k}")
               for k, v in items[i:i+2]]
        rows.append(row)
    return InlineKeyboardMarkup(rows)

def _voice_keyboard() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(v, callback_data=f"voice:{k}")]
            for k, v in VOICES.items()]
    return InlineKeyboardMarkup(rows)

def _upload_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📤 Upload TikTok", callback_data="upload:yes"),
        InlineKeyboardButton("⏭️ Bỏ qua",        callback_data="upload:no"),
    ]])

def _user_settings(ctx: ContextTypes.DEFAULT_TYPE) -> dict:
    ud = ctx.user_data
    return {
        "genre": ud.get("genre", config.DEFAULT_GENRE),
        "voice": ud.get("voice", config.DEFAULT_VOICE),
        "mode":  ud.get("mode",  "story"),
    }

async def _typing(update: Update):
    await update.effective_chat.send_action(ChatAction.TYPING)

async def _upload_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                        video_path: str, caption: str):
    """Gửi file video về Telegram + upload TikTok nếu có cấu hình."""
    chat_id = update.effective_chat.id

    # Gửi về Telegram
    await ctx.bot.send_message(chat_id, "📤 Đang gửi video...")
    with open(video_path, "rb") as f:
        await ctx.bot.send_video(
            chat_id, f,
            caption=caption[:1024],
            supports_streaming=True,
        )

    # Upload TikTok (nếu đã cấu hình)
    if uploader.configured:
        await ctx.bot.send_message(chat_id, "⏳ Đang upload lên TikTok...")
        try:
            result = uploader.upload(video_path, caption)
            await ctx.bot.send_message(
                chat_id,
                f"✅ Đã upload TikTok!\n`publish_id`: `{result['publish_id']}`",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            await ctx.bot.send_message(chat_id, f"⚠️ Upload TikTok thất bại: {e}")
    else:
        await ctx.bot.send_message(
            chat_id,
            "ℹ️ TikTok chưa cấu hình — video đã gửi về Telegram.\n"
            "Thêm `TIKTOK_ACCESS_TOKEN` vào `.env` để bật auto-upload.",
        )

# ── Core pipeline ──────────────────────────────────────────────────────────────
async def _run_story_flow(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                          user_prompt: str, mode: str = "story"):
    """Toàn bộ flow: viết truyện → pipeline → gửi video."""
    chat_id = update.effective_chat.id
    settings = _user_settings(ctx)
    genre    = settings["genre"]
    voice    = settings["voice"]

    username = update.effective_user.username or ""

    status_msg = await ctx.bot.send_message(
        chat_id, "✍️ *Đang viết truyện...*", parse_mode=ParseMode.MARKDOWN
    )

    async def progress(step: str, pct: int):
        try:
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            await status_msg.edit_text(
                f"{step}\n`[{bar}] {pct}%`",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass

    # Bước 1 — Viết truyện
    await ctx.bot.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        story_text = await asyncio.get_event_loop().run_in_executor(
            None, write_story, user_prompt, genre, mode
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi khi viết truyện: {e}")
        return

    # Gửi truyện text về Telegram
    story_preview = story_text[:3000] + ("..." if len(story_text) > 3000 else "")
    await ctx.bot.send_message(
        chat_id,
        f"📖 *Nội dung truyện:*\n\n{story_preview}",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Bước 2 — Tạo hook + caption
    await progress("🔗 Tạo hook & caption...", 15)
    try:
        hook_text = await asyncio.get_event_loop().run_in_executor(
            None, generate_hook, story_text, genre
        )
        caption = await asyncio.get_event_loop().run_in_executor(
            None, generate_caption, story_text, genre
        )
    except Exception as e:
        hook_text = ""
        caption   = story_text[:150] + "..."

    # Bước 3 — Chạy pipeline tạo video
    try:
        result = await run_pipeline(
            story_text=story_text,
            genre=genre,
            voice=voice,
            hook_text=hook_text,
            username=username,
            progress_callback=progress,
        )
    except Exception as e:
        log.error(traceback.format_exc())
        await status_msg.edit_text(f"❌ Lỗi pipeline: {e}")
        return

    video_path = result["video_path"]
    duration   = result["duration"]

    await status_msg.edit_text(
        f"🎉 *Xong!* Video `{duration:.0f}s`\nĐang chuẩn bị gửi...",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Bước 4 — Gửi video
    await _upload_video(update, ctx, video_path, caption)

    # Dọn file tạm
    try:
        os.remove(video_path)
    except Exception:
        pass

# ── Handlers ───────────────────────────────────────────────────────────────────
@restricted
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    provider_label = {
        "anthropic":  "☁️ Claude API (Anthropic)",
        "groq":       "⚡ Llama 3.3 (Groq — free)",
        "claude-cli": "🍎 Claude CLI (macOS app)",
    }.get(AI_PROVIDER, "❓ Chưa cấu hình")
    text = (
        "👋 *AutoPost Bot* — Viết truyện & đăng TikTok tự động!\n\n"
        f"🧠 AI đang dùng: *{provider_label}*\n\n"
        "📌 *Lệnh chính:*\n"
        "• `/story <nội dung>` — Viết truyện phong cách NNA rồi tạo video\n"
        "• `/poem <nội dung>` — Viết thơ phong cách NPV rồi tạo video\n\n"
        "⚙️ *Tuỳ chỉnh:*\n"
        "• `/genres` — Chọn thể loại\n"
        "• `/voices` — Chọn giọng đọc\n"
        "• `/settings` — Xem cài đặt hiện tại\n\n"
        "💡 *Ví dụ:*\n"
        "`/story Hai đứa bạn thân hồi cấp 3 gặp lại nhau sau 10 năm`\n"
        "`/poem Nhớ ai đó nhưng không dám gọi điện`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


@restricted
async def cmd_story(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(ctx.args).strip()
    if not prompt:
        await update.message.reply_text(
            "❓ Vui lòng nhập chủ đề.\nVD: `/story Cô gái quên mang ô khi trời mưa`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await _run_story_flow(update, ctx, prompt, mode="story")


@restricted
async def cmd_poem(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(ctx.args).strip()
    if not prompt:
        await update.message.reply_text(
            "❓ Vui lòng nhập chủ đề.\nVD: `/poem Cô đơn giữa thành phố đông người`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    await _run_story_flow(update, ctx, prompt, mode="poem")


@restricted
async def cmd_genres(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    current = ctx.user_data.get("genre", config.DEFAULT_GENRE)
    label   = GENRES.get(current, current)
    await update.message.reply_text(
        f"🎭 Chọn thể loại (hiện tại: *{label}*)",
        reply_markup=_genre_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@restricted
async def cmd_voices(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    current = ctx.user_data.get("voice", config.DEFAULT_VOICE)
    label   = VOICES.get(current, current)
    await update.message.reply_text(
        f"🎙️ Chọn giọng đọc (hiện tại: *{label}*)",
        reply_markup=_voice_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@restricted
async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    s = _user_settings(ctx)
    text = (
        "⚙️ *Cài đặt hiện tại:*\n\n"
        f"• Thể loại: *{GENRES.get(s['genre'], s['genre'])}*\n"
        f"• Giọng đọc: *{VOICES.get(s['voice'], s['voice'])}*\n"
        f"• Chế độ: *{'Truyện' if s['mode'] == 'story' else 'Thơ'}*\n\n"
        "Dùng `/genres` và `/voices` để thay đổi."
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cb_genre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    genre = query.data.split(":")[1]
    ctx.user_data["genre"] = genre
    label = GENRES.get(genre, genre)
    await query.edit_message_text(f"✅ Đã chọn thể loại: *{label}*", parse_mode=ParseMode.MARKDOWN)


async def cb_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    voice = query.data.split(":")[1]
    ctx.user_data["voice"] = voice
    label = VOICES.get(voice, voice)
    await query.edit_message_text(f"✅ Đã chọn giọng: *{label}*", parse_mode=ParseMode.MARKDOWN)


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    log.error("Exception:", exc_info=ctx.error)

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("❌ TELEGRAM_BOT_TOKEN chưa được thiết lập trong .env")
    if config.AI_PROVIDER == "none":
        raise SystemExit(
            "❌ Chưa cấu hình AI provider. Chọn 1 trong 3:\n"
            "   1. Cài Claude Code CLI + đăng nhập  (claude.ai/code)\n"
            "   2. GROQ_API_KEY=...   trong .env  (console.groq.com — miễn phí)\n"
            "   3. ANTHROPIC_API_KEY= trong .env  (console.anthropic.com)"
        )
    log.info(f"🤖 AI provider: {config.AI_PROVIDER.upper()}")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("story",    cmd_story))
    app.add_handler(CommandHandler("poem",     cmd_poem))
    app.add_handler(CommandHandler("genres",   cmd_genres))
    app.add_handler(CommandHandler("voices",   cmd_voices))
    app.add_handler(CommandHandler("settings", cmd_settings))

    app.add_handler(CallbackQueryHandler(cb_genre, pattern=r"^genre:"))
    app.add_handler(CallbackQueryHandler(cb_voice, pattern=r"^voice:"))

    app.add_error_handler(on_error)

    # Đăng ký lệnh cho Telegram menu
    async def post_init(app):
        await app.bot.set_my_commands([
            BotCommand("start",    "Hướng dẫn sử dụng"),
            BotCommand("story",    "Viết truyện NNA + tạo video TikTok"),
            BotCommand("poem",     "Viết thơ NPV + tạo video TikTok"),
            BotCommand("genres",   "Chọn thể loại"),
            BotCommand("voices",   "Chọn giọng đọc"),
            BotCommand("settings", "Xem cài đặt hiện tại"),
        ])

    app.post_init = post_init

    log.info("🤖 Bot đang chạy... Nhấn Ctrl+C để dừng.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
