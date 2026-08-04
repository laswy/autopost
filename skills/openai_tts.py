"""
OpenAI TTS — tạo audio dùng gpt-4o-mini-tts (hoặc tts-1-hd).
Fallback sang edge-tts nếu không có OPENAI_API_KEY.

Voices khuyến nghị:
  alloy  — trung tính, rõ ràng, phù hợp học thuật
  nova   — nữ, tự nhiên, thân thiện
  echo   — nam, trầm, chắc chắn
  shimmer— nữ, nhẹ nhàng, ấm áp
  onyx   — nam, chuyên nghiệp
"""

import asyncio
import json
import os
import time
from pathlib import Path

from config import OPENAI_API_KEY, TTS_PROVIDER

# Point pydub at static binaries if system ones are broken
import pydub.utils as _pu
if not _pu.which("ffprobe") or os.path.exists("/usr/local/bin/ffprobe"):
    os.environ.setdefault("PATH", "/usr/local/bin:" + os.environ.get("PATH", ""))

# Semaphore: limit gTTS to 1 concurrent request to avoid 429
_GTTS_SEM = asyncio.Semaphore(1)


# ── OpenAI TTS ────────────────────────────────────────────────────────────────

def _openai_tts_sync(text: str, output_path: str, voice: str = "alloy",
                     model: str = "gpt-4o-mini-tts") -> None:
    """Tạo audio bằng OpenAI TTS (blocking)."""
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)

    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    ) as resp:
        resp.stream_to_file(output_path)


async def openai_tts_segment(seg: dict, voice: str, job_dir: Path) -> dict:
    """Async wrapper cho OpenAI TTS — không có word timing."""
    i   = seg["id"]
    mp3 = job_dir / f"voice_{i}.mp3"

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _openai_tts_sync, seg["text"], str(mp3), voice)

    # Lấy duration từ file audio
    from pydub import AudioSegment
    audio    = AudioSegment.from_mp3(str(mp3))
    duration = len(audio) / 1000.0

    # Không có word timing với OpenAI TTS — dùng dict rỗng
    tmg = job_dir / f"timing_{i}.json"
    tmg.write_text("[]", encoding="utf-8")

    return {**seg, "mp3": str(mp3), "timing": str(tmg), "duration": duration}


# ── gTTS (Google TTS) — fallback miễn phí ────────────────────────────────────

def _gtts_lang(voice: str) -> str:
    """Map voice name → ngôn ngữ gTTS."""
    voice = voice.lower()
    if "vi" in voice or voice in ("shimmer", "nova", "alloy", "echo", "onyx", "fable"):
        return "vi"
    return "en"

def _gtts_lang_lesson(voice: str) -> str:
    """Bài học tiếng Anh luôn đọc bằng en."""
    return "en"

async def gtts_segment(seg: dict, voice: str, job_dir: Path,
                        lang: str = "") -> dict:
    """gTTS — dùng Google TTS, không cần API key. Giới hạn 1 request đồng thời."""
    from gtts import gTTS
    from pydub import AudioSegment

    i   = seg["id"]
    mp3 = job_dir / f"voice_{i}.mp3"
    tmg = job_dir / f"timing_{i}.json"

    if not lang:
        lang = _gtts_lang(voice)

    loop = asyncio.get_event_loop()

    for attempt in range(4):
        try:
            async with _GTTS_SEM:
                def _gen():
                    tts = gTTS(text=seg["text"], lang=lang, slow=False)
                    tts.save(str(mp3))
                await loop.run_in_executor(None, _gen)
            break
        except Exception as e:
            if attempt == 3:
                raise
            wait = 2 ** attempt
            await asyncio.sleep(wait)

    audio    = AudioSegment.from_mp3(str(mp3))
    duration = len(audio) / 1000.0

    tmg.write_text("[]", encoding="utf-8")
    return {**seg, "mp3": str(mp3), "timing": str(tmg), "duration": duration}


# ── edge-tts ──────────────────────────────────────────────────────────────────

async def edge_tts_segment(seg: dict, voice: str, job_dir: Path) -> dict:
    """edge-tts — miễn phí, có word timing. Fallback sang gTTS nếu SSL lỗi."""
    import edge_tts

    i   = seg["id"]
    mp3 = job_dir / f"voice_{i}.mp3"
    tmg = job_dir / f"timing_{i}.json"

    try:
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

    except Exception:
        # SSL hoặc network lỗi → fallback gTTS
        lang = "vi" if "vi-VN" in voice else "en"
        return await gtts_segment(seg, voice, job_dir, lang=lang)


# ── Dispatcher ────────────────────────────────────────────────────────────────

async def tts_segment(seg: dict, voice: str, job_dir: Path) -> dict:
    """
    Tạo audio cho 1 segment — tự chọn provider dựa theo TTS_PROVIDER.

    voice:
      OpenAI: alloy | nova | echo | shimmer | onyx | fable
      edge-tts: vi-VN-HoaiMyNeural | vi-VN-NamMinhNeural | en-US-JennyNeural ...
    """
    if TTS_PROVIDER == "openai":
        return await openai_tts_segment(seg, voice, job_dir)
    else:
        return await edge_tts_segment(seg, voice, job_dir)


async def tts_all(segments: list[dict], voice: str, job_dir: Path) -> list[dict]:
    tasks = [tts_segment(seg, voice, job_dir) for seg in segments]
    return list(await asyncio.gather(*tasks))


# ── Voice lists ───────────────────────────────────────────────────────────────

OPENAI_VOICES = {
    "alloy":   "🔵 Alloy (trung tính, rõ ràng)",
    "nova":    "🟣 Nova (nữ, thân thiện)",
    "echo":    "🟢 Echo (nam, trầm)",
    "shimmer": "🟡 Shimmer (nữ, nhẹ nhàng)",
    "onyx":    "⚫ Onyx (nam, chuyên nghiệp)",
    "fable":   "🟠 Fable (kể chuyện)",
}

EDGE_VOICES = {
    "vi-VN-HoaiMyNeural":  "🇻🇳 Hoài My (nữ, VI)",
    "vi-VN-NamMinhNeural": "🇻🇳 Nam Minh (nam, VI)",
    "en-US-JennyNeural":   "🇺🇸 Jenny (nữ, EN)",
    "en-US-GuyNeural":     "🇺🇸 Guy (nam, EN)",
}

def available_voices() -> dict:
    return OPENAI_VOICES if TTS_PROVIDER == "openai" else EDGE_VOICES

def default_lesson_voice() -> str:
    """Giọng mặc định cho bài học tiếng Anh."""
    return "nova" if TTS_PROVIDER == "openai" else "en-US-JennyNeural"

def default_story_voice() -> str:
    """Giọng mặc định cho truyện tiếng Việt."""
    return "shimmer" if TTS_PROVIDER == "openai" else "vi-VN-HoaiMyNeural"
