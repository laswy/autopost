"""
NNA Writer skill — gọi Claude API để viết truyện/thơ theo phong cách
Nguyễn Nhật Ánh (NNA) và Nguyễn Phong Việt (NPV).
"""

import anthropic
from config import ANTHROPIC_API_KEY

# Toàn bộ system prompt được chiết xuất từ SKILL.md của nna-writer
_SYSTEM_PROMPT = """Bạn là người kể chuyện & làm thơ nắm vững hai trường phái:

- NNA (Nguyễn Nhật Ánh): Ngôn ngữ giản dị mà tinh tế, hài hước không cần cố gắng, mỗi câu chuyện nhỏ đều chứa một suy nghĩ lớn. Ấm áp, không phán xét, bao giờ cũng có một chút hài — vì cuộc đời thật ra vừa buồn vừa buồn cười cùng một lúc.

- NPV (Nguyễn Phong Việt): Thơ đô thị hiện đại, ngôn ngữ của thế hệ sống trong căn phòng một mình giữa thành phố đông người. Không cần vần điệu hoàn hảo, chỉ cần mỗi dòng chạm đúng một chỗ đang đau.

## QUY TẮC GIỌNG VĂN NNA

1. Ngôi thứ nhất, kể như đang nhớ lại — "Hồi đó tôi không biết rằng..."
2. So sánh bất ngờ nhưng đúng — không "ghen như lửa đốt" mà "ghen kiểu ngứa ngáy không gãi được"
3. Triết lý từ quan sát nhỏ, KHÔNG thuyết giáo — để chi tiết tự nói
4. Hài hước đến từ sự thật — buồn cười nhất khi nhân vật biết mình đang ngốc mà vẫn không dừng được
5. Không ai hoàn toàn đúng, không ai hoàn toàn sai
6. Đau nhẹ hơn bi thảm — buồn nhẹ hơn tuyệt vọng
7. Kết thúc mở — cuộc đời sau chia tay vẫn có buổi sáng

## QUY TẮC THƠ NPV

1. Ngôn ngữ đời thường — "căn phòng này thiếu một người" không phải "trống vắng bao la"
2. Hình ảnh cụ thể: "3 giờ sáng" / "ly trà đã nguội" / "đèn đường màu vàng"
3. Cảm xúc suy ra từ hành động — không "tôi rất cô đơn" mà "tôi đặt thêm một cái ly / rồi lại cất đi"
4. Dòng cuối thường ngắn, đơn giản, nặng
5. TRÁNH: từ Hán-Việt nặng nề, vần điệu gượng ép, kết thúc có moral rõ ràng

## ĐỊNH DẠNG OUTPUT

Khi viết truyện: trả lời văn xuôi liền mạch, đủ để đọc 3–10 phút.
Khi viết thơ: xuống dòng tự nhiên, khoảng cách đoạn 1 dòng trống.
KHÔNG thêm lời giải thích trước hoặc sau nội dung sáng tác."""


def write_story(prompt: str, genre: str = "romance", mode: str = "story") -> str:
    """
    Gọi Claude để viết truyện hoặc thơ.

    Args:
        prompt: Yêu cầu từ người dùng (chủ đề, nhân vật, cảm xúc...)
        genre:  Thể loại — romance / horror / motivational / mystery / general
        mode:   "story" (truyện NNA) hoặc "poem" (thơ NPV) hoặc "auto"

    Returns:
        Nội dung truyện/thơ dạng string
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    if mode == "story":
        instruction = f"Viết truyện ngắn phong cách NNA (Nguyễn Nhật Ánh), thể loại {genre}. Độ dài khoảng 600–1000 từ, đủ hấp dẫn để nghe dưới dạng audio TikTok."
    elif mode == "poem":
        instruction = "Viết một bài thơ phong cách NPV (Nguyễn Phong Việt). Dài 20–30 dòng."
    else:
        instruction = f"Tự quyết định viết truyện hay thơ phù hợp nhất với yêu cầu. Thể loại: {genre}."

    user_message = f"{instruction}\n\nYêu cầu: {prompt}"

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text


def generate_hook(story_text: str, genre: str) -> str:
    """Tạo câu hook hấp dẫn cho TikTok dựa trên nội dung truyện."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": (
                f"Dựa vào đoạn truyện sau, viết 1 câu hook mở đầu TikTok cực kỳ hấp dẫn "
                f"(dưới 20 chữ, có emoji, thể loại {genre}).\n"
                f"Chỉ trả lời câu hook, không giải thích.\n\n"
                f"Truyện:\n{story_text[:300]}"
            )
        }],
    )

    return message.content[0].text.strip()


def generate_caption(story_text: str, genre: str) -> str:
    """Tạo caption TikTok + hashtag từ nội dung truyện."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                f"Viết caption TikTok cho video kể chuyện thể loại {genre}. Gồm:\n"
                f"1. Hook đầu (1 câu có emoji)\n"
                f"2. Tóm tắt hấp dẫn (2-3 câu)\n"
                f"3. CTA: 'Theo dõi để nghe phần tiếp theo! 🔔'\n"
                f"4. 15–20 hashtag phù hợp (tiếng Việt + tiếng Anh + #fyp)\n\n"
                f"Nội dung truyện:\n{story_text[:400]}\n\n"
                f"Chỉ trả lời caption, không giải thích."
            )
        }],
    )

    return message.content[0].text.strip()
