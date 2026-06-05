"""
TikTok Content Posting API v2 — upload video lên TikTok.
Tham khảo: story-to-tiktok/references/tiktok-upload.md
"""

import math
import os
import requests
from config import (
    TIKTOK_ACCESS_TOKEN, TIKTOK_CLIENT_KEY,
    TIKTOK_CLIENT_SECRET, TIKTOK_REFRESH_TOKEN,
)

_BASE = "https://open.tiktokapis.com/v2"


class TikTokUploader:
    def __init__(self):
        self.access_token  = TIKTOK_ACCESS_TOKEN
        self.client_key    = TIKTOK_CLIENT_KEY
        self.client_secret = TIKTOK_CLIENT_SECRET
        self.refresh_token = TIKTOK_REFRESH_TOKEN

    @property
    def configured(self) -> bool:
        return bool(self.access_token and self.client_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        }

    def refresh_access_token(self) -> str:
        resp = requests.post(f"{_BASE}/oauth/token/", data={
            "client_key":    self.client_key,
            "client_secret": self.client_secret,
            "grant_type":    "refresh_token",
            "refresh_token": self.refresh_token,
        })
        data = resp.json()
        self.access_token = data["access_token"]
        return self.access_token

    def _init_upload(self, video_size: int, caption: str) -> dict:
        chunk_size   = 10 * 1024 * 1024  # 10 MB
        total_chunks = math.ceil(video_size / chunk_size)

        body = {
            "post_info": {
                "title":           caption[:150],
                "privacy_level":   "SELF_ONLY",  # đổi thành PUBLIC_TO_EVERYONE khi sẵn sàng
                "disable_duet":    False,
                "disable_comment": False,
                "disable_stitch":  False,
            },
            "source_info": {
                "source":             "FILE_UPLOAD",
                "video_size":         video_size,
                "chunk_size":         chunk_size,
                "total_chunk_count":  total_chunks,
            },
        }
        resp = requests.post(
            f"{_BASE}/post/publish/video/init/",
            headers=self._headers(),
            json=body,
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def _upload_chunks(self, upload_url: str, video_path: str) -> None:
        chunk_size  = 10 * 1024 * 1024
        video_size  = os.path.getsize(video_path)
        total       = math.ceil(video_size / chunk_size)

        with open(video_path, "rb") as f:
            for i in range(total):
                data  = f.read(chunk_size)
                start = i * chunk_size
                end   = min(start + len(data) - 1, video_size - 1)
                resp  = requests.put(
                    upload_url,
                    headers={
                        "Content-Range":  f"bytes {start}-{end}/{video_size}",
                        "Content-Length": str(len(data)),
                        "Content-Type":   "video/mp4",
                    },
                    data=data,
                )
                resp.raise_for_status()

    def _check_status(self, publish_id: str) -> dict:
        resp = requests.post(
            f"{_BASE}/post/publish/status/fetch/",
            headers=self._headers(),
            json={"publish_id": publish_id},
        )
        resp.raise_for_status()
        return resp.json()["data"]

    def upload(self, video_path: str, caption: str) -> dict:
        """
        Upload video lên TikTok.

        Returns:
            dict với "publish_id" và "status"
        Raises:
            RuntimeError nếu chưa cấu hình TikTok credentials
        """
        if not self.configured:
            raise RuntimeError(
                "TikTok chưa được cấu hình. "
                "Vui lòng thiết lập TIKTOK_ACCESS_TOKEN và TIKTOK_CLIENT_KEY trong .env"
            )

        video_size  = os.path.getsize(video_path)
        init_data   = self._init_upload(video_size, caption)
        upload_url  = init_data["upload_url"]
        publish_id  = init_data["publish_id"]

        self._upload_chunks(upload_url, video_path)

        status = self._check_status(publish_id)
        return {"publish_id": publish_id, "status": status}


uploader = TikTokUploader()
