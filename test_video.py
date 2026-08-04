#!/usr/bin/env python3
"""
Test script — tạo video bài học tiếng Anh không cần bot/AI.
Dùng nội dung hardcode để test pipeline nhanh.
"""
import asyncio, os, sys
sys.path.insert(0, "/home/user/autopost")
os.environ["TTS_PROVIDER"] = "edge"  # dùng edge-tts miễn phí

from skills.openai_tts import tts_all
from skills.lesson_pipeline import run_lesson_pipeline

# Nội dung bài học hardcode (không cần gọi AI)
LESSON = {
    "hook": "Bạn có biết 5 từ này không? 🤔",
    "title": "Daily Routines — Thói quen hàng ngày",
    "items": [
        {
            "word": "wake up",
            "phonetic": "/weɪk ʌp/",
            "meaning": "thức dậy",
            "example": "I wake up at 6 AM every day.",
            "example_vi": "Tôi thức dậy lúc 6 giờ sáng mỗi ngày."
        },
        {
            "word": "have breakfast",
            "phonetic": "/hæv ˈbrekfəst/",
            "meaning": "ăn sáng",
            "example": "She always has breakfast before going to work.",
            "example_vi": "Cô ấy luôn ăn sáng trước khi đi làm."
        },
        {
            "word": "commute",
            "phonetic": "/kəˈmjuːt/",
            "meaning": "đi làm / di chuyển đến nơi làm việc",
            "example": "He commutes to work by motorbike.",
            "example_vi": "Anh ấy đi làm bằng xe máy."
        },
    ],
    "tip": "Dùng simple present để nói về thói quen: I wake up, She eats, He goes...",
    "cta": "Theo dõi để học tiếng Anh mỗi ngày! 🔔",
    "caption": "#hoctienganh #english #dailyroutines #tiktokviệtnam #fyp",
    "script": ""
}

async def main():
    from skills.english_lesson import lesson_to_segments
    segments = lesson_to_segments(LESSON)
    print(f"✅ {len(segments)} segments")
    for s in segments:
        print(f"  [{s['type']}] {s['text'][:60]}")

    print("\n🎙️  Tạo TTS (edge-tts)...")
    result = await run_lesson_pipeline(
        lesson=LESSON,
        segments=segments,
        voice="en-US-JennyNeural",
        progress_callback=None,
    )
    print(f"\n🎉 Video: {result['video_path']}")
    print(f"   Thời lượng: {result['duration']:.1f}s")
    print(f"   Size: {os.path.getsize(result['video_path'])//1024} KB")

asyncio.run(main())
