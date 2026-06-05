"""
NNA Writer skill — viết truyện/thơ phong cách NNA/NPV.
Hỗ trợ: Anthropic Claude (ưu tiên) hoặc Groq + Llama (miễn phí).
"""

from config import AI_PROVIDER, ANTHROPIC_API_KEY, GROQ_API_KEY

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


def _call_anthropic(system: str, user: str, max_tokens: int = 4096, fast: bool = False) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    model  = "claude-haiku-4-5-20251001" if fast else "claude-opus-4-8"
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _call_groq(system: str, user: str, max_tokens: int = 4096, fast: bool = False) -> str:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    # llama-3.3-70b-versatile: chất lượng tốt nhất trên Groq (miễn phí)
    # llama-3.1-8b-instant: nhanh hơn cho các tác vụ nhỏ
    model = "llama-3.1-8b-instant" if fast else "llama-3.3-70b-versatile"
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content


def _call_ai(system: str, user: str, max_tokens: int = 4096, fast: bool = False) -> str:
    """Gọi AI provider được cấu hình, raise RuntimeError nếu chưa cấu hình."""
    if AI_PROVIDER == "anthropic":
        return _call_anthropic(system, user, max_tokens, fast)
    elif AI_PROVIDER == "groq":
        return _call_groq(system, user, max_tokens, fast)
    else:
        raise RuntimeError(
            "Chưa cấu hình AI provider.\n"
            "• Thêm ANTHROPIC_API_KEY=... vào .env  (console.anthropic.com)\n"
            "• Hoặc GROQ_API_KEY=...  vào .env  (console.groq.com — miễn phí)"
        )


def write_story(prompt: str, genre: str = "romance", mode: str = "story") -> str:
    """
    Viết truyện (NNA) hoặc thơ (NPV).

    Args:
        prompt: Yêu cầu từ người dùng
        genre:  romance / horror / motivational / mystery / general
        mode:   "story" | "poem" | "auto"
    """
    if mode == "story":
        instruction = (
            f"Viết truyện ngắn phong cách NNA (Nguyễn Nhật Ánh), thể loại {genre}. "
            f"Độ dài khoảng 600–1000 từ, đủ hấp dẫn để nghe dưới dạng audio TikTok."
        )
    elif mode == "poem":
        instruction = "Viết một bài thơ phong cách NPV (Nguyễn Phong Việt). Dài 20–30 dòng."
    else:
        instruction = f"Tự quyết định viết truyện hay thơ phù hợp nhất với yêu cầu. Thể loại: {genre}."

    return _call_ai(_SYSTEM_PROMPT, f"{instruction}\n\nYêu cầu: {prompt}", max_tokens=4096)


def generate_hook(story_text: str, genre: str) -> str:
    """Tạo câu hook hấp dẫn cho TikTok."""
    system = "Bạn là chuyên gia viết hook TikTok. Chỉ trả lời đúng 1 câu hook, không giải thích."
    user   = (
        f"Viết 1 câu hook mở đầu TikTok cực kỳ hấp dẫn (dưới 20 chữ, có emoji, "
        f"thể loại {genre}) cho truyện sau:\n\n{story_text[:300]}"
    )
    return _call_ai(system, user, max_tokens=100, fast=True)


def generate_caption(story_text: str, genre: str) -> str:
    """Tạo caption TikTok + hashtag."""
    system = "Bạn là chuyên gia content TikTok. Chỉ trả lời caption, không giải thích thêm."
    user   = (
        f"Viết caption TikTok cho video kể chuyện thể loại {genre}. Gồm:\n"
        f"1. Hook đầu (1 câu có emoji)\n"
        f"2. Tóm tắt hấp dẫn (2-3 câu)\n"
        f"3. CTA: 'Theo dõi để nghe phần tiếp theo! 🔔'\n"
        f"4. 15–20 hashtag phù hợp (tiếng Việt + tiếng Anh + #fyp)\n\n"
        f"Nội dung truyện:\n{story_text[:400]}"
    )
    return _call_ai(system, user, max_tokens=500, fast=True)
