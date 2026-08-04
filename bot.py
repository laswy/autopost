#!/usr/bin/env python3
"""
AutoPost Telegram Bot
━━━━━━━━━━━━━━━━━━━━
Nhận lệnh từ Telegram, viết truyện/thơ/bài học tiếng Anh bằng AI,
chuyển thành video TikTok 9:16 rồi upload hoặc gửi về Telegram.

Lệnh:
  /start              — Hướng dẫn sử dụng
  /story <prompt>     — Viết truyện NNA + tạo video
  /poem <prompt>      — Viết thơ NPV + tạo video
  /lesson <chủ đề>    — Tạo bài học tiếng Anh (vocabulary mặc định)
  /vocab <chủ đề>     — Bài học từ vựng
  /phrase <chủ đề>    — Bài học cụm từ / idiom
  /grammar <chủ đề>   — Bài học ngữ pháp
  /voices             — Danh sách giọng đọc
  /genres             — Danh sách thể loại (chỉ cho story/poem)
  /settings           — Xem cài đặt hiện tại
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
from config import AI_PROVIDER, TTS_PROVIDER
from skills.nna_writer import write_story, generate_hook, generate_caption
from skills.story_pipeline import run_pipeline
from skills.english_lesson import generate_lesson, lesson_to_segments
from skills.lesson_pipeline import run_lesson_pipeline
from skills.openai_tts import available_voices, default_lesson_voice, default_story_voice
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

LESSON_TYPES = {
    "vocabulary":    "📚 Từ vựng",
    "phrase":        "💬 Cụm từ / Idiom",
    "grammar":       "📝 Ngữ pháp",
    "pronunciation": "🔊 Phát âm",
}

# VOICES được load động từ TTS provider
def _get_voices() -> dict:
    return available_voices()

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
            for k, v in _get_voices().items()]
    return InlineKeyboardMarkup(rows)

def _lesson_type_keyboard() -> InlineKeyboardMarkup:
    rows = []
    items = list(LESSON_TYPES.items())
    for i in range(0, len(items), 2):
        row = [InlineKeyboardButton(v, callback_data=f"ltype:{k}")
               for k, v in items[i:i+2]]
        rows.append(row)
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
    tts_lbl = "🔵 OpenAI TTS" if TTS_PROVIDER == "openai" else "🆓 edge-tts"
    text = (
        "👋 *AutoPost Bot* — Viết truyện & học tiếng Anh, đăng TikTok tự động!\n\n"
        f"🧠 AI: *{provider_label}* | 🎙️ TTS: *{tts_lbl}*\n\n"
        "📖 *Truyện & Thơ:*\n"
        "• `/story <chủ đề>` — Viết truyện phong cách NNA\n"
        "• `/poem <chủ đề>` — Viết thơ phong cách NPV\n\n"
        "🇺🇸 *Học Tiếng Anh:*\n"
        "• `/lesson <chủ đề>` — Bài học tổng hợp\n"
        "• `/vocab <chủ đề>` — Từ vựng\n"
        "• `/phrase <chủ đề>` — Cụm từ / Idiom\n"
        "• `/grammar <chủ đề>` — Ngữ pháp\n\n"
        "⚙️ *Tuỳ chỉnh:*\n"
        "• `/genres` `/voices` `/settings`\n\n"
        "💡 *Ví dụ:*\n"
        "`/story Hai người bạn gặp lại sau 10 năm`\n"
        "`/vocab job interview`\n"
        "`/phrase travel English`\n"
        "`/grammar present perfect`"
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
async def cmd_lesson(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                     lesson_type: str = "vocabulary"):
    """Tạo bài học tiếng Anh từ chủ đề — pipeline riêng với OpenAI TTS."""
    topic = " ".join(ctx.args).strip()
    if not topic:
        await update.message.reply_text(
            "❓ Vui lòng nhập chủ đề.\n"
            "VD: `/lesson daily routines`\n"
            "     `/vocab job interview`\n"
            "     `/phrase travel English`\n"
            "     `/grammar present perfect`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    chat_id  = update.effective_chat.id
    voice    = ctx.user_data.get("lesson_voice", default_lesson_voice())
    lt_label = LESSON_TYPES.get(lesson_type, lesson_type)

    status_msg = await ctx.bot.send_message(
        chat_id,
        f"🇺🇸 *Đang tạo bài học tiếng Anh...*\n"
        f"Chủ đề: `{topic}` | Loại: {lt_label}",
        parse_mode=ParseMode.MARKDOWN,
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

    # Bước 1 — Tạo nội dung bài học
    await progress("🧠 AI đang soạn bài học...", 10)
    try:
        lesson = await asyncio.get_event_loop().run_in_executor(
            None, generate_lesson, topic, lesson_type
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi tạo bài học: {e}")
        return

    # Gửi preview nội dung
    preview = f"📚 *{lesson.get('title', topic)}*\n\n"
    for item in lesson.get("items", [])[:3]:
        preview += f"• *{item['word']}* {item.get('phonetic','')} — {item['meaning']}\n"
        preview += f"  _{item.get('example','')}_\n"
    if lesson.get("tip"):
        preview += f"\n💡 {lesson['tip']}"
    await ctx.bot.send_message(chat_id, preview, parse_mode=ParseMode.MARKDOWN)

    # Bước 2 — Tạo segments
    segments = lesson_to_segments(lesson)

    # Bước 3 — Pipeline video
    try:
        result = await run_lesson_pipeline(
            lesson=lesson,
            segments=segments,
            voice=voice,
            progress_callback=progress,
        )
    except Exception as e:
        log.error(traceback.format_exc())
        await status_msg.edit_text(f"❌ Lỗi tạo video: {e}")
        return

    video_path = result["video_path"]
    caption    = result["caption"]
    duration   = result["duration"]

    await status_msg.edit_text(
        f"🎉 *Bài học hoàn thành!* `{duration:.0f}s`\nĐang gửi video...",
        parse_mode=ParseMode.MARKDOWN,
    )
    await _upload_video(update, ctx, video_path, caption)

    try:
        os.remove(video_path)
    except Exception:
        pass


@restricted
async def cmd_vocab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_lesson(update, ctx, lesson_type="vocabulary")

@restricted
async def cmd_phrase(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_lesson(update, ctx, lesson_type="phrase")

@restricted
async def cmd_grammar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await cmd_lesson(update, ctx, lesson_type="grammar")


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
    voices  = _get_voices()
    current = ctx.user_data.get("voice", default_story_voice())
    label   = voices.get(current, current)
    tts_lbl = "🔵 OpenAI TTS" if TTS_PROVIDER == "openai" else "🆓 edge-tts"
    await update.message.reply_text(
        f"🎙️ Chọn giọng đọc — *{tts_lbl}*\n(hiện tại: *{label}*)",
        reply_markup=_voice_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


@restricted
async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    voices  = _get_voices()
    s       = _user_settings(ctx)
    v_story = ctx.user_data.get("voice", default_story_voice())
    v_lesson= ctx.user_data.get("lesson_voice", default_lesson_voice())
    ai_lbl  = {"anthropic": "☁️ Claude API", "groq": "⚡ Groq Llama",
                "claude-cli": "🍎 Claude CLI"}.get(AI_PROVIDER, "❓")
    tts_lbl = "🔵 OpenAI TTS (gpt-4o-mini-tts)" if TTS_PROVIDER == "openai" else "🆓 edge-tts"
    text = (
        "⚙️ *Cài đặt hiện tại:*\n\n"
        f"🧠 AI: *{ai_lbl}*\n"
        f"🎙️ TTS: *{tts_lbl}*\n\n"
        f"📖 Story/Poem:\n"
        f"  • Thể loại: *{GENRES.get(s['genre'], s['genre'])}*\n"
        f"  • Giọng: *{voices.get(v_story, v_story)}*\n\n"
        f"🇺🇸 Lesson:\n"
        f"  • Giọng: *{voices.get(v_lesson, v_lesson)}*\n\n"
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
    query  = update.callback_query
    await query.answer()
    voice  = query.data.split(":")[1]
    voices = _get_voices()
    # Lưu cho cả story và lesson — user có thể dùng cùng giọng
    ctx.user_data["voice"]        = voice
    ctx.user_data["lesson_voice"] = voice
    label = voices.get(voice, voice)
    await query.edit_message_text(f"✅ Đã chọn giọng: *{label}*\n_(áp dụng cho cả story & lesson)_",
                                  parse_mode=ParseMode.MARKDOWN)


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
    app.add_handler(CommandHandler("lesson",   cmd_lesson))
    app.add_handler(CommandHandler("vocab",    cmd_vocab))
    app.add_handler(CommandHandler("phrase",   cmd_phrase))
    app.add_handler(CommandHandler("grammar",  cmd_grammar))
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
            BotCommand("lesson",   "Bài học tiếng Anh (từ vựng mặc định)"),
            BotCommand("vocab",    "Học từ vựng tiếng Anh"),
            BotCommand("phrase",   "Học cụm từ / idiom tiếng Anh"),
            BotCommand("grammar",  "Học ngữ pháp tiếng Anh"),
            BotCommand("genres",   "Chọn thể loại story/poem"),
            BotCommand("voices",   "Chọn giọng đọc TTS"),
            BotCommand("settings", "Xem cài đặt hiện tại"),
        ])

    app.post_init = post_init

    log.info("🤖 Bot đang chạy... Nhấn Ctrl+C để dừng.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
