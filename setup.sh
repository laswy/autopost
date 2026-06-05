#!/bin/bash
# Cài đặt môi trường cho AutoPost Bot

set -e

echo "📦 Cài đặt dependencies Python..."
pip install -r requirements.txt --break-system-packages --quiet

echo "🛠️  Kiểm tra ffmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg chưa có — đang cài..."
    sudo apt-get install -y ffmpeg 2>/dev/null || brew install ffmpeg 2>/dev/null || \
        echo "❌ Cài ffmpeg thủ công: https://ffmpeg.org/download.html"
else
    echo "✅ ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
fi

echo ""
echo "📁 Tạo thư mục..."
mkdir -p assets work_dir output

if [ ! -f assets/font.ttf ]; then
    echo "🔤 Tải font BeVietnamPro-Bold..."
    curl -sL "https://github.com/googlefonts/BeVietnamPro/raw/main/fonts/ttf/BeVietnamPro-Bold.ttf" \
         -o assets/font.ttf 2>/dev/null || \
    echo "⚠️  Tải font thủ công: đặt file .ttf vào assets/font.ttf"
fi

echo ""
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Đã tạo .env — điền API keys vào file này!"
else
    echo "✅ .env đã tồn tại"
fi

echo ""
echo "🚀 Cài đặt xong! Chạy bot:"
echo "   python bot.py"
