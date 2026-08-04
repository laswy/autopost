"""
Lesson → TikTok Video Pipeline
Tạo video bài học tiếng Anh 9:16 với layout card chuyên biệt.

Frame layout cho mỗi loại segment:
  hook        — nền xanh navy, text lớn màu vàng
  lesson_item — nền tối, card trắng chứa: word lớn / phonetic / meaning / example
  tip         — nền tím, icon 💡, text mẹo
  cta         — nền xanh lá, CTA text + follow reminder
"""

import asyncio
import os
import textwrap
import time
import uuid
from pathlib import Path

from config import WORK_DIR, OUTPUT_DIR, FONT_PATH
from skills.openai_tts import tts_all

# ── Video config ───────────────────────────────────────────────────────────────
W, H  = 1080, 1920
FPS   = 30

# Màu nền theo loại segment
BG_COLORS = {
    "hook":        (10, 20, 60),    # xanh navy đậm
    "lesson_item": (15, 15, 25),    # tối
    "tip":         (40, 10, 60),    # tím
    "cta":         (10, 45, 20),    # xanh lá
}

# ── Frame creators ─────────────────────────────────────────────────────────────

def _load_font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _draw_rounded_rect(draw, xy, radius: int, fill):
    """Vẽ hình chữ nhật bo góc bằng Pillow."""
    from PIL import ImageDraw
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + 2*radius, y0 + 2*radius], fill=fill)
    draw.ellipse([x1 - 2*radius, y0, x1, y0 + 2*radius], fill=fill)
    draw.ellipse([x0, y1 - 2*radius, x0 + 2*radius, y1], fill=fill)
    draw.ellipse([x1 - 2*radius, y1 - 2*radius, x1, y1], fill=fill)


def make_hook_frame(seg: dict) -> "Image":
    from PIL import Image, ImageDraw
    img  = Image.new("RGB", (W, H), BG_COLORS["hook"])
    draw = ImageDraw.Draw(img)

    d = seg.get("display", {})
    main = d.get("main", seg["text"])
    sub  = d.get("sub", "")

    # Accent line trên cùng
    draw.rectangle([0, 0, W, 12], fill=(255, 200, 0))

    f_main = _load_font(80)
    f_sub  = _load_font(52)
    f_tag  = _load_font(38)

    # Tag "ENGLISH TODAY"
    draw.text((W//2, 200), "🇺🇸 ENGLISH TODAY", font=f_tag,
              fill=(180, 180, 255), anchor="mm")

    # Main hook
    wrapped = textwrap.fill(main, width=18)
    # shadow
    draw.multiline_text((W//2+3, H//2-60+3), wrapped, font=f_main,
                        fill=(0,0,0), anchor="mm", align="center")
    draw.multiline_text((W//2, H//2-60), wrapped, font=f_main,
                        fill=(255, 220, 50), anchor="mm", align="center",
                        stroke_width=2, stroke_fill=(0,0,0))

    # Sub (lesson title)
    if sub:
        draw.text((W//2, H//2 + 120), sub, font=f_sub,
                  fill=(200, 220, 255), anchor="mm")

    _draw_branding(draw)
    return img


def make_lesson_item_frame(seg: dict) -> "Image":
    """Card bài học: word lớn ở giữa, phonetic, nghĩa, ví dụ."""
    from PIL import Image, ImageDraw
    img  = Image.new("RGB", (W, H), BG_COLORS["lesson_item"])
    draw = ImageDraw.Draw(img)

    d        = seg.get("display", {})
    word     = d.get("word",       seg["text"][:30])
    phonetic = d.get("phonetic",   "")
    meaning  = d.get("meaning",    "")
    example  = d.get("example",    "")
    example_vi = d.get("example_vi", "")

    f_word    = _load_font(96)
    f_phonetic= _load_font(44)
    f_meaning = _load_font(54)
    f_example = _load_font(40)
    f_label   = _load_font(34)

    # Card nền trắng mờ
    card_x0, card_y0 = 60, H//2 - 480
    card_x1, card_y1 = W - 60, H//2 + 480
    _draw_rounded_rect(draw, (card_x0, card_y0, card_x1, card_y1), 40, (30, 30, 50))

    cx = W // 2
    y  = card_y0 + 80

    # Word
    draw.text((cx, y), word, font=f_word,
              fill=(255, 220, 50), anchor="mm",
              stroke_width=2, stroke_fill=(0,0,0))
    y += 110

    # Phonetic
    if phonetic:
        draw.text((cx, y), phonetic, font=f_phonetic,
                  fill=(150, 200, 255), anchor="mm")
        y += 70

    # Divider
    draw.rectangle([card_x0+60, y, card_x1-60, y+3], fill=(80, 80, 120))
    y += 30

    # Label + meaning
    draw.text((cx, y+10), "NGHĨA:", font=f_label, fill=(140,140,180), anchor="mm")
    y += 50
    wrapped_mean = textwrap.fill(meaning, width=24)
    draw.multiline_text((cx, y), wrapped_mean, font=f_meaning,
                        fill=(255, 255, 255), anchor="mm", align="center")
    y += 40 * (wrapped_mean.count("\n") + 1) + 30

    # Divider
    draw.rectangle([card_x0+60, y, card_x1-60, y+3], fill=(80, 80, 120))
    y += 30

    # Example EN
    if example:
        draw.text((cx, y+10), "VÍ DỤ:", font=f_label, fill=(140,140,180), anchor="mm")
        y += 50
        wrapped_ex = textwrap.fill(f'"{example}"', width=26)
        draw.multiline_text((cx, y), wrapped_ex, font=f_example,
                            fill=(180, 230, 180), anchor="mm", align="center",
                            stroke_width=1, stroke_fill=(0,0,0))
        y += 44 * (wrapped_ex.count("\n") + 1) + 15

    # Example VI
    if example_vi:
        wrapped_vi = textwrap.fill(example_vi, width=28)
        draw.multiline_text((cx, y), wrapped_vi, font=f_example,
                            fill=(160, 160, 200), anchor="mm", align="center")

    _draw_branding(draw)
    return img


def make_tip_frame(seg: dict) -> "Image":
    from PIL import Image, ImageDraw
    img  = Image.new("RGB", (W, H), BG_COLORS["tip"])
    draw = ImageDraw.Draw(img)

    d    = seg.get("display", {})
    main = d.get("main", "💡 Mẹo")
    sub  = d.get("sub",  seg["text"])

    f_icon = _load_font(120)
    f_title= _load_font(64)
    f_text = _load_font(50)

    draw.text((W//2, H//2 - 200), "💡", font=f_icon, anchor="mm")
    draw.text((W//2, H//2 - 60),  "MẸO GHI NHỚ", font=f_title,
              fill=(255, 220, 80), anchor="mm")

    wrapped = textwrap.fill(sub, width=22)
    draw.multiline_text((W//2, H//2 + 80), wrapped, font=f_text,
                        fill=(230, 210, 255), anchor="mm", align="center",
                        stroke_width=1, stroke_fill=(0,0,0))

    _draw_branding(draw)
    return img


def make_cta_frame(seg: dict) -> "Image":
    from PIL import Image, ImageDraw
    img  = Image.new("RGB", (W, H), BG_COLORS["cta"])
    draw = ImageDraw.Draw(img)

    d    = seg.get("display", {})
    main = d.get("main", seg["text"])

    f_big   = _load_font(72)
    f_small = _load_font(48)

    draw.text((W//2, H//2 - 120), "🔔", font=f_big,  anchor="mm")
    wrapped = textwrap.fill(main, width=22)
    draw.multiline_text((W//2, H//2 + 40), wrapped, font=f_big,
                        fill=(200, 255, 200), anchor="mm", align="center",
                        stroke_width=2, stroke_fill=(0,0,0))
    draw.text((W//2, H//2 + 220), "Follow • Like • Comment", font=f_small,
              fill=(150, 220, 150), anchor="mm")

    _draw_branding(draw)
    return img


def _draw_branding(draw, text: str = "English Every Day 🇺🇸"):
    f = _load_font(34)
    draw.text((W//2, H - 70), text, font=f, fill=(120, 120, 140), anchor="mm")


_FRAME_MAKERS = {
    "hook":        make_hook_frame,
    "lesson_item": make_lesson_item_frame,
    "tip":         make_tip_frame,
    "cta":         make_cta_frame,
}


def make_clip(seg: dict, job_dir: Path):
    from moviepy import ImageClip, AudioFileClip

    maker      = _FRAME_MAKERS.get(seg["type"], make_hook_frame)
    img        = maker(seg)
    frame_path = str(job_dir / f"frame_{seg['id']}.png")
    img.save(frame_path)

    audio = AudioFileClip(seg["mp3"])
    return ImageClip(frame_path).with_duration(audio.duration).with_audio(audio)


# ── Full pipeline ──────────────────────────────────────────────────────────────

async def run_lesson_pipeline(
    lesson: dict,
    segments: list[dict],
    voice: str = "nova",
    progress_callback=None,
) -> dict:
    """
    Chạy pipeline: segments → TTS → frames → video.

    Args:
        lesson:            Output của english_lesson.generate_lesson()
        segments:          Output của english_lesson.lesson_to_segments()
        voice:             Giọng đọc (OpenAI: nova/alloy/... | edge: en-US-JennyNeural/...)
        progress_callback: async callable(step, pct)

    Returns:
        dict với "video_path", "duration", "caption"
    """
    job_id  = f"lesson_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    job_dir = Path(WORK_DIR) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    async def notify(step: str, pct: int):
        if progress_callback:
            await progress_callback(step, pct)

    await notify("🎙️ Tạo giọng đọc OpenAI TTS...", 20)
    segments = await tts_all(segments, voice, job_dir)

    await notify("🎨 Tạo frame bài học...", 50)
    loop = asyncio.get_event_loop()
    video_path = await loop.run_in_executor(
        None, _export_video, segments, job_id, job_dir
    )

    total = sum(s["duration"] for s in segments)
    await notify("✅ Video hoàn thành!", 100)

    return {
        "video_path": video_path,
        "duration":   total,
        "caption":    lesson.get("caption", ""),
        "job_id":     job_id,
    }


def _export_video(segments: list[dict], job_id: str, job_dir: Path) -> str:
    from moviepy import concatenate_videoclips

    clips = [make_clip(seg, job_dir) for seg in segments]
    final = concatenate_videoclips(clips, method="chain")
    out   = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")
    final.write_videofile(
        out, fps=FPS, codec="libx264",
        audio_codec="aac", bitrate="4000k",
        preset="fast", logger=None,
    )
    return out
