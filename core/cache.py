import os
import json
import hashlib
import time
from typing import Optional, Any
from core.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# Thư mục mặc định lưu file cache
DEFAULT_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "query_cache")


class FileCache:
    """
    Hệ thống Cache bằng file JSON trên ổ cứng.
    Mục đích: Nếu user hỏi lại câu cũ (hoặc câu tương tự),
    hệ thống sẽ trả kết quả từ cache NGAY LẬP TỨC mà không cần
    gọi LLM hay chạy SQL lại → Tiết kiệm API calls (FREE tier).
    
    Mỗi entry cache là 1 file JSON:
    data/query_cache/
    ├── a1b2c3d4.json   ← hash của câu SQL
    ├── e5f6g7h8.json
    └── ...
    """

    def __init__(self, cache_dir: str = None, default_ttl: int = None):
        self.cache_dir = os.path.abspath(cache_dir or DEFAULT_CACHE_DIR)
        self.default_ttl = default_ttl or settings.CACHE_TTL  # Mặc định 300 giây (5 phút)
        os.makedirs(self.cache_dir, exist_ok=True)

    def cache_key(self, text: str, user_attributes: dict = None) -> str:
        """Tạo key duy nhất bằng SHA256 (Kết hợp Text và Quyền User để bảo mật RLS)."""
        raw_string = text
        if user_attributes:
            raw_string += "_" + json.dumps(user_attributes, sort_keys=True)
        return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()[:16]

    def _filepath(self, key: str) -> str:
        """Trả về đường dẫn tới file cache."""
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, key: str) -> Optional[Any]:
        """
        Đọc cache theo key.
        Trả về None nếu: chưa có cache, hoặc cache đã hết hạn.
        """
        filepath = self._filepath(key)

        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cached = json.load(f)

            # Kiểm tra hết hạn (TTL)
            if time.time() > cached.get("expires_at", 0):
                os.remove(filepath)
                logger.debug(f"Cache expired, đã xóa: {key}")
                return None

            logger.info(f"Cache HIT: {key}")
            return cached.get("data")

        except (json.JSONDecodeError, IOError):
            return None

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Lưu data vào cache (Hỗ trợ Pydantic và Ghi nguyên tử chống lỗi đồng thời)."""
        ttl = ttl or self.default_ttl
        filepath = self._filepath(key)

        # Chuyển đổi Pydantic model thành dict trước khi lưu
        if hasattr(value, "model_dump"):
            value = value.model_dump()

        cached = {
            "data": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl
        }

        # Ghi nguyên tử (Atomic Write) bằng file tạm để chống lỗi đụng độ khi có nhiều người dùng
        temp_filepath = f"{filepath}.tmp"
        try:
            with open(temp_filepath, "w", encoding="utf-8") as f:
                json.dump(cached, f, ensure_ascii=False, indent=2, default=str)
            os.replace(temp_filepath, filepath) # Thao tác tráo đổi chỉ mất 1 nano-giây
            logger.debug(f"Cache SET: {key}, TTL={ttl}s")
        except Exception as e:
            logger.error(f"Lỗi khi ghi cache {key}: {e}")
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

    def delete(self, key: str) -> None:
        """Xóa một entry cache."""
        filepath = self._filepath(key)
        if os.path.exists(filepath):
            os.remove(filepath)

    def clear_expired(self) -> int:
        """Dọn dẹp tất cả cache đã hết hạn. Trả về số lượng file đã xóa."""
        count = 0
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(self.cache_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if time.time() > cached.get("expires_at", 0):
                    os.remove(filepath)
                    count += 1
            except Exception:
                pass

        if count > 0:
            logger.info(f"Đã dọn {count} file cache hết hạn")
        return count

    def clear_all(self) -> int:
        """Xóa toàn bộ cache (dùng khi reset hệ thống)."""
        count = 0
        for filename in os.listdir(self.cache_dir):
            filepath = os.path.join(self.cache_dir, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
                count += 1
        logger.info(f"Đã xóa toàn bộ {count} file cache")
        return count