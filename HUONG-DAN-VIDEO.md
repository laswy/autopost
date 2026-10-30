# HƯỚNG DẪN TẠO VIDEO TRUYỆN (đặt trong thư mục autopost trên máy Cò)

Tệp này là "trí nhớ" của agent chạy trên máy Cò. Agent phải đọc hết tệp này trước khi làm video. Cò dạy thêm bằng cách ghi vào mục "BÀI HỌC CỦA CÒ" ở cuối tệp. Mỗi bài học mới ghi đè mọi điều cũ nếu mâu thuẫn.

## 1. MỤC TIÊU VÀ GIỚI HẠN
1. Làm video dọc 9:16 (1080x1920, 24 fps), hoạt hình 2D, nhân vật nói thoại, phụ đề trắng viền đen, từ một đoạn hay của truyện trên web "Đọc Đêm".
2. Chỉ làm video và lưu file. KHÔNG đăng lên TikTok, Facebook, Ayrshare hay mạng xã hội nào. KHÔNG gọi tiktok_upload.py.
3. Giọng đọc là giọng của Cò (OmniVoice) cho mọi nhân vật. Chỉ nhân bản giọng của chính Cò.
4. Video dài 30 đến 45 giây, 6 đến 10 dòng thoại, mỗi dòng không quá 15 từ.
5. Luôn trả lời Cò bằng tiếng Việt, ngắn, danh sách số 1, 2, 3, không dùng dấu "-".

## 2. THƯ MỤC VÀ CÔNG CỤ
1. Gốc dự án: `~/autopost`. Máy dựng video: `skills/cartoon_video.py`.
2. Python của OmniVoice: `~/autopost/.venv-omnivoice/bin/python`. Máy chủ giọng: `tools/giong_co_app.py` (cổng 7861, API `/doc`).
3. Làm việc trong `work_dir/video_<ten-truyen>/`. Video thành phẩm vào `output/`.
4. Phần mềm cần có: ffmpeg, MoviePy 2.x, Pillow, edge-tts (chỉ khi cần giọng dự phòng), font `assets/font.ttf`.
5. Nếu thiếu thứ gì, nói rõ thiếu gì và cách cài, đừng tắt kiểm tra TLS và đừng bỏ qua bước.

## 3. QUY TRÌNH (làm đúng thứ tự)
1. Chọn đoạn: đọc chương truyện Cò chỉ định (hoặc chọn đoạn cảm xúc nhất, có hội thoại 2 người). Tóm tắt lý do chọn trong 1 câu.
2. Viết kịch bản thoại: 6 đến 10 dòng. Dòng đầu là lời dẫn, dòng cuối là lời dẫn kêu gọi đọc truyện trên Đọc Đêm. Giữ nguyên tên nhân vật, thuật ngữ đã chốt của truyện.
3. Cho Cò duyệt kịch bản (bảng: số, người nói, câu, thời lượng dự kiến). Chưa duyệt thì chưa làm tiếp.
4. Tạo giọng: với mỗi dòng gọi API `/doc` của máy chủ OmniVoice (tốc độ 1.1), lưu `work_dir/video_<ten>/01.wav`, `02.wav`, ... theo số dòng. Nhân vật khác nhau chỉ khác tốc độ và ngắt nghỉ, vẫn là giọng Cò.
5. Viết `spec.json` (mẫu ở mục 4). Mỗi dòng thoại có `"audio": "đường/dẫn/NN.wav"`. Nếu dòng có `audio`, máy dựng bỏ qua edge-tts và mở miệng theo độ lớn tiếng.
6. Dựng: `cd ~/autopost && python3 -m skills.cartoon_video work_dir/video_<ten>/spec.json output/<ten>.mp4`.
7. Kiểm tra: `ffprobe` lấy thời lượng (30 đến 45 giây), trích 3 khung hình bằng ffmpeg (đầu, giữa, cuối) và xem. Phụ đề phải nằm ở khoảng giữa dưới khung hình, không che mặt, không tràn lề, chữ Việt đủ dấu.
8. Báo cáo cho Cò: đường dẫn file, thời lượng, 3 ý đã kiểm tra, và caption gợi ý kèm 5 hashtag. Không đăng.

## 4. MẪU spec.json
```json
{
  "title": "Ấm Trà Vạn Cổ", "brand": "Đọc Đêm",
  "characters": {
    "vong": {"look": "man", "pitch": "+6Hz", "skin": [245,210,175], "hair": [30,24,28],
             "shirt": [120,130,150], "clothes": "shirt", "room": "quan", "tag": "TRÀ QUÁN VỌNG TUYẾT"},
    "di":   {"look": "old_woman", "pitch": "-6Hz", "skin": [240,200,165], "hair": [150,150,156],
             "shirt": [70,110,150], "clothes": "shirt", "flip": true, "room": "quan", "tag": "TRÀ QUÁN VỌNG TUYẾT"},
    "narrator": {"room": "quan"}
  },
  "lines": [
    {"who": "narrator", "text": "Lời dẫn mở đầu.", "emo": "neutral", "audio": "work_dir/video_x/01.wav",
     "card": {"kind": "note", "title": "TIÊU ĐỀ THẺ", "lines": ["ý 1", "ý 2", "ý 3"]}},
    {"who": "vong", "text": "Câu thoại.", "emo": "sad", "audio": "work_dir/video_x/02.wav"}
  ]
}
```
Quy ước:
1. `emo`: neutral, happy, sad, surprised, worried, angry, teary, sleep.
2. `look`: man, woman, old_woman. `clothes`: hoodie, tee, apron, shirt. `room`: bep, phong, quan, xuong. `flip` lật nhân vật để hai người nhìn vào nhau (người thứ hai đặt `flip: true`).
3. `card.kind`: note (tiêu đề và 3 dòng), grid, image (có `path` ảnh bìa). Chỉ dùng thẻ ở dòng lời dẫn đầu, tối đa 2 thẻ cả video.
4. `tag` là nhãn địa điểm trên đầu khung hình, viết hoa, ngắn.
5. Màu da, tóc, áo chọn để hai nhân vật dễ phân biệt. Không dùng hai nhân vật cùng màu áo.
6. Truyện tiên hiệp: chưa có trang phục riêng, dùng `shirt` màu chàm hoặc xám và phòng `quan`. Cần trang phục mới thì báo Cò, đừng tự vẽ lại cả bộ máy.

## 5. TIÊU CHÍ ĐẠT
1. Khẩu hình mở đúng lúc có tiếng, đóng khi nghỉ.
2. Mỗi dòng thoại hiện đúng phụ đề của nó, không tràn quá 2 dòng chữ.
3. Có đủ thẻ mở đầu, hội thoại, lời kêu gọi cuối.
4. Âm lượng đều, không bị cắt cụt đầu hoặc đuôi câu (máy dựng đã chừa 0,22 giây nghỉ sau mỗi dòng).
5. Không có chữ lỗi font (ô vuông), không mất dấu tiếng Việt.

## 6. XỬ LÝ LỖI THƯỜNG GẶP
1. Máy chủ OmniVoice không lên: chạy `Doc_giong_Co.command`, chờ tới khi `http://127.0.0.1:7861` trả lời, xem log `work_dir/giong_co_app.log`.
2. Lỗi `box can't exceed original image size`: bản cartoon_video cũ, cập nhật lại từ GitHub (`git pull`).
3. Miệng không mở: tệp wav quá nhỏ tiếng hoặc quá nhiều nhiễu nền. Đọc lại ở chỗ yên tĩnh, hoặc chuẩn hóa âm lượng bằng ffmpeg `loudnorm`.
4. Lỗi SSL khi dùng edge-tts: đặt `SSL_CERT_FILE` trỏ đến gói chứng chỉ của hệ thống, tuyệt đối không tắt xác thực.

## 7. BÀI HỌC CỦA CÒ
Cò ghi thêm bên dưới, mỗi bài một số. Agent đọc từ trên xuống và làm theo.
1. (trống, chờ Cò dạy)
