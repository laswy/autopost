"""
English Lesson Generator — tạo nội dung bài học tiếng Anh theo format TikTok.
Dùng cùng AI provider với nna_writer (anthropic / groq / claude-cli).
"""

import json
from skills.nna_writer import _call_ai

_LESSON_SYSTEM = """Bạn là giáo viên tiếng Anh chuyên tạo nội dung học thuật ngắn gọn, hấp dẫn cho TikTok.
Phong cách: rõ ràng, thực tế, có ví dụ đời thường, giải thích bằng tiếng Việt.
Luôn trả lời đúng định dạng JSON được yêu cầu, không thêm bất kỳ text nào bên ngoài JSON."""


def generate_lesson(topic: str, lesson_type: str = "vocabulary") -> dict:
    """
    Tạo nội dung 1 bài học tiếng Anh.

    Args:
        topic:       Chủ đề — VD: "daily routines", "job interview", "travel", "phrasal verbs"
        lesson_type: vocabulary | phrase | grammar | pronunciation

    Returns:
        dict với các trường:
          hook          — câu hook mở đầu TikTok (tiếng Việt, có emoji)
          title         — tiêu đề bài học (EN)
          items         — list[dict] các mục học (tối đa 5)
            word/phrase — từ/cụm từ tiếng Anh
            phonetic    — phiên âm IPA
            meaning     — nghĩa tiếng Việt
            example     — câu ví dụ tiếng Anh
            example_vi  — dịch câu ví dụ
          tip           — mẹo ghi nhớ hoặc lưu ý quan trọng
          cta           — câu CTA kết thúc (tiếng Việt)
          caption       — caption TikTok đầy đủ (hook + tóm tắt + CTA + hashtag)
          script        — toàn bộ nội dung đọc (cho TTS), tiếng Anh xen Việt
    """
    type_instruction = {
        "vocabulary": (
            "Chọn 3–5 từ vựng tiếng Anh quan trọng, thông dụng liên quan đến chủ đề. "
            "Mỗi từ có phiên âm IPA, nghĩa tiếng Việt, 1 câu ví dụ tự nhiên."
        ),
        "phrase": (
            "Chọn 3–5 cụm từ / idiom / collocations thông dụng liên quan đến chủ đề. "
            "Ưu tiên các cụm từ người bản ngữ dùng hàng ngày, không quá sách vở."
        ),
        "grammar": (
            "Giải thích 1 điểm ngữ pháp quan trọng liên quan đến chủ đề. "
            "Dùng 3–4 ví dụ so sánh đúng/sai hoặc các biến thể khác nhau."
        ),
        "pronunciation": (
            "Chọn 3–5 từ/âm tiếng Anh thường phát âm sai. "
            "Giải thích cách phát âm đúng kèm mẹo ghi nhớ."
        ),
    }.get(lesson_type, "Chọn 3–5 điểm học thực tế liên quan đến chủ đề.")

    prompt = f"""Tạo bài học tiếng Anh TikTok về chủ đề: "{topic}"
Loại bài: {lesson_type}
{type_instruction}

Trả về JSON theo cấu trúc sau (không thêm text ngoài JSON):
{{
  "hook": "câu hook tiếng Việt có emoji, tối đa 15 chữ",
  "title": "Tiêu đề bài học tiếng Anh ngắn gọn",
  "items": [
    {{
      "word": "từ hoặc cụm từ tiếng Anh",
      "phonetic": "/phiên âm IPA/",
      "meaning": "nghĩa tiếng Việt",
      "example": "Example sentence in English.",
      "example_vi": "Dịch câu ví dụ sang tiếng Việt."
    }}
  ],
  "tip": "1 mẹo ghi nhớ hoặc lưu ý quan trọng (tiếng Việt)",
  "cta": "câu CTA kết thúc video (tiếng Việt, có emoji)",
  "caption": "caption TikTok đầy đủ: hook + nội dung tóm tắt + CTA + 15-20 hashtag",
  "script": "toàn bộ script đọc cho TTS — xen tiếng Anh và tiếng Việt tự nhiên, khoảng 200-300 chữ"
}}"""

    raw = _call_ai(_LESSON_SYSTEM, prompt, max_tokens=2048)

    # Parse JSON — bỏ qua markdown code block nếu model thêm vào
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    if text.endswith("```"):
        text = text[:-3]

    return json.loads(text.strip())


def lesson_to_segments(lesson: dict) -> list[dict]:
    """
    Chuyển lesson dict thành danh sách segments cho pipeline video.
    Mỗi segment = 1 màn hình card trên video.
    """
    segments = []

    # Segment 0 — Hook
    segments.append({
        "id": 0,
        "type": "hook",
        "text": lesson["hook"],
        "display": {
            "main": lesson["hook"],
            "sub":  lesson["title"],
        },
    })

    # Segment 1..N — Từng item học
    for i, item in enumerate(lesson.get("items", []), start=1):
        text_for_tts = (
            f"{item['word']}. "
            f"{item['word']}. "
            f"Nghĩa là: {item['meaning']}. "
            f"Ví dụ: {item['example']} — {item['example_vi']}."
        )
        segments.append({
            "id": i,
            "type": "lesson_item",
            "text": text_for_tts,
            "display": {
                "word":       item["word"],
                "phonetic":   item.get("phonetic", ""),
                "meaning":    item["meaning"],
                "example":    item["example"],
                "example_vi": item.get("example_vi", ""),
            },
        })

    # Segment tip
    tip_id = len(segments)
    segments.append({
        "id": tip_id,
        "type": "tip",
        "text": f"Mẹo: {lesson['tip']}",
        "display": {"main": "💡 Mẹo", "sub": lesson["tip"]},
    })

    # Segment CTA
    cta_id = len(segments)
    segments.append({
        "id": cta_id,
        "type": "cta",
        "text": lesson["cta"],
        "display": {"main": lesson["cta"]},
    })

    return segments
