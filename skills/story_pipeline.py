"""
Story → TikTok pipeline — chuyển đổi văn bản thành video MP4 9:16.
Dựa trên story-to-tiktok skill với một số cải tiến cho Telegram bot.
"""

import asyncio
import json
import os
import re
import textwrap
import time
import uuid
from pathlib import Path

from config import WORK_DIR, OUTPUT_DIR, FONT_PATH

# ── Cài đặt video ─────────────────────────────────────────────────────────────
W, H           = 1080, 1920
FPS            = 30
BG_COLOR       = (15, 15, 30)
TEXT_COLOR     = (255, 255, 255)
ACTIVE_COLOR   = (255, 220, 0)
FONT_SIZE      = 68
BRAND_FONT_SIZE = 36
MAX_WORDS_SEG  = 45


# ── Step 1: Split ─────────────────────────────────────────────────────────────

def split_story(story_text: str, genre: str, hook_text: str = "") -> list[dict]:
    """Chia truyện thành các segment ngắn, thêm hook + CTA."""
    text = story_text.strip()
    sentences = re.split(r'(?<=[.!?…»])\s+', text)

    segments_raw = []
    current: list[str] = []
    current_len = 0

    for sent in sentences:
        wc = len(sent.split())
        if current_len + wc > MAX_WORDS_SEG and current:
            segments_raw.append(" ".join(current))
            current = [sent]
            current_len = wc
        else:
            current.append(sent)
            current_len += wc

    if current:
        segments_raw.append(" ".join(current))

    hook = hook_text or _default_hook(genre)
    cta  = "Theo dõi để nghe phần tiếp theo nhé! 🔔 Like nếu bạn thích câu chuyện này! ❤️"

    result = [{"id": 0, "type": "hook",  "text": hook}]
    for i, seg in enumerate(segments_raw, start=1):
        result.append({"id": i, "type": "story", "text": seg})
    result.append({"id": len(result), "type": "cta", "text": cta})

    return result


def _default_hook(genre: str) -> str:
    hooks = {
        "horror":       "Câu chuyện này sẽ khiến bạn không dám ngủ một mình... 👻",
        "romance":      "Đây là câu chuyện tình yêu buồn nhất tôi từng nghe... 💔",
        "motivational": "Từ con số 0, anh ta đã làm được điều không ai tin... 🔥",
        "mystery":      "Vụ án này chưa bao giờ có lời giải... cho đến hôm nay 🔎",
        "general":      "Câu chuyện này sẽ khiến bạn suy nghĩ mãi... 👀",
    }
    return hooks.get(genre, hooks["general"])


# ── Step 2: TTS ───────────────────────────────────────────────────────────────

async def tts_segment(seg: dict, voice: str, job_dir: Path) -> dict:
    """Tạo file audio cho 1 segment bằng edge-tts."""
    import edge_tts

    i   = seg["id"]
    mp3 = job_dir / f"voice_{i}.mp3"
    tmg = job_dir / f"timing_{i}.json"

    communicate = edge_tts.Communicate(seg["text"], voice, rate="-10%")
    timings: list[dict] = []

    with open(mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                timings.append({
                    "word":  chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "end":   (chunk["offset"] + chunk["duration"]) / 10_000_000,
                })

    with open(tmg, "w", encoding="utf-8") as f:
        json.dump(timings, f, ensure_ascii=False)

    duration = timings[-1]["end"] if timings else 2.0
    return {**seg, "mp3": str(mp3), "timing": str(tmg), "duration": duration}


async def tts_all(segments: list[dict], voice: str, job_dir: Path) -> list[dict]:
    tasks = [tts_segment(seg, voice, job_dir) for seg in segments]
    return list(await asyncio.gather(*tasks))


# ── Step 3+4: Frame + subtitle ────────────────────────────────────────────────

def _get_font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _bg_color_for_type(seg_type: str) -> tuple:
    if seg_type == "hook":
        return (30, 10, 10)
    if seg_type == "cta":
        return (10, 25, 10)
    return BG_COLOR


def create_frame(seg: dict, username: str = "") -> "Image":
    from PIL import Image, ImageDraw

    bg = _bg_color_for_type(seg["type"])
    img  = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Gradient overlay (đơn giản)
    for y in range(H):
        alpha = int(30 * (1 - y / H))
        draw.line([(0, y), (W, y)], fill=(alpha, alpha, alpha + 10))

    font  = _get_font(FONT_SIZE)
    bfont = _get_font(BRAND_FONT_SIZE)

    text_color = ACTIVE_COLOR if seg["type"] == "hook" else TEXT_COLOR

    wrapped = textwrap.fill(seg["text"], width=20)

    # shadow
    draw.multiline_text(
        (W // 2 + 4, H // 2 + 4), wrapped,
        font=font, fill=(0, 0, 0), anchor="mm", align="center"
    )
    # main text
    draw.multiline_text(
        (W // 2, H // 2), wrapped,
        font=font, fill=text_color, anchor="mm", align="center",
        stroke_width=2, stroke_fill=(0, 0, 0)
    )

    # branding
    brand = f"@{username} • Theo dõi để nghe thêm truyện hay 🔔" if username else "Theo dõi để nghe thêm truyện hay 🔔"
    draw.text(
        (W // 2, H - 80), brand,
        font=bfont, fill=(160, 160, 160), anchor="mm"
    )

    return img


def make_clip(seg: dict, username: str = ""):
    """Tạo MoviePy clip từ 1 segment."""
    from moviepy.editor import ImageClip, AudioFileClip
    from pathlib import Path

    frame_path = str(Path(seg["mp3"]).parent / f"frame_{seg['id']}.png")
    img = create_frame(seg, username)
    img.save(frame_path)

    audio = AudioFileClip(seg["mp3"])
    clip  = ImageClip(frame_path).set_duration(audio.duration).set_audio(audio)
    return clip


# ── Step 5+6: Export ──────────────────────────────────────────────────────────

def export_video(segments: list[dict], job_id: str, username: str = "") -> str:
    from moviepy.editor import concatenate_videoclips

    clips = [make_clip(seg, username) for seg in segments]
    final = concatenate_videoclips(clips, method="compose")

    out_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
    final.write_videofile(
        out_path,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        bitrate="4000k",
        preset="fast",
        logger=None,
    )
    return out_path


# ── Full pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline(
    story_text: str,
    genre: str = "romance",
    voice: str = "vi-VN-HoaiMyNeural",
    hook_text: str = "",
    username: str = "",
    progress_callback=None,
) -> dict:
    """
    Chạy toàn bộ pipeline story → video.

    Args:
        story_text:        Nội dung truyện
        genre:             Thể loại video
        voice:             Giọng TTS (edge-tts)
        hook_text:         Câu hook tùy chỉnh (để trống = tự tạo)
        username:          TikTok/Telegram username để watermark
        progress_callback: async callable(step: str, pct: int) để cập nhật tiến độ

    Returns:
        dict với "video_path", "duration", "segments"
    """
    job_id  = f"{int(time.time())}_{uuid.uuid4().hex[:6]}"
    job_dir = Path(WORK_DIR) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    async def notify(step: str, pct: int):
        if progress_callback:
            await progress_callback(step, pct)

    await notify("📝 Chia đoạn truyện...", 10)
    segments = split_story(story_text, genre, hook_text)

    # Save segments.json
    with open(job_dir / "segments.json", "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    await notify("🎙️ Tạo giọng đọc TTS...", 25)
    segments = await tts_all(segments, voice, job_dir)

    await notify("🎬 Tạo frame video...", 55)
    # export_video chạy blocking — chạy trong executor để không block event loop
    loop = asyncio.get_event_loop()
    video_path = await loop.run_in_executor(
        None, export_video, segments, job_id, username
    )

    total_duration = sum(s["duration"] for s in segments)

    await notify("✅ Hoàn thành!", 100)

    return {
        "video_path": video_path,
        "duration":   total_duration,
        "segments":   segments,
        "job_id":     job_id,
    }
