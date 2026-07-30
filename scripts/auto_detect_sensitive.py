"""
AUTO DETECT SENSITIVE COLUMNS — AI Tự Động Quét Cột Nhạy Cảm

Luồng chạy:
1. Kết nối Database → Lấy toàn bộ Schema (Bảng + Cột + Kiểu dữ liệu + Dữ liệu mẫu).
2. Ném cho Gemini đóng vai Chuyên gia Bảo mật Dữ liệu (Data Privacy Officer).
3. Gemini phân loại từng cột vào 3 nhóm:
   - "exclude": Cấm tuyệt đối (Password, Token, Mã thẻ tín dụng).
   - "mask":    Cho truy vấn nhưng che giấu kết quả (SĐT, Email, CCCD, Lương).
   - "safe":    An toàn, không cần xử lý gì.
4. Ghi kết quả vào config/sensitive_columns.json.

Cách chạy:
    python scripts/auto_detect_sensitive.py
"""
import os
import sys
import json
import re

# Thêm root_dir vào sys.path để import được các module từ thư mục cha
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv()

from core.logger import get_logger
from config.settings import settings
from modules.data_source.base import get_connector
from modules.schema.engine import SchemaEngine
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Bảng màu cho Terminal
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

# Đảm bảo UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Đường dẫn file kết quả
SENSITIVE_CONFIG_PATH = os.path.join(root_dir, "config", "sensitive_columns.json")


def detect_sensitive_columns():
    """Hàm chính: Quét Schema bằng AI và ghi kết quả vào sensitive_columns.json."""
    
    print(f"\n{C.CYAN}{C.BOLD}KHOI DONG HE THONG AI QUET COT NHAY CAM{C.RESET}")
    print(f"{C.CYAN}{'='*70}{C.RESET}")

    # ── BƯỚC 1: Kết nối Database ──
    print(f"{C.YELLOW}[1/4] Ket noi Database...{C.RESET}", end=" ")
    connector = get_connector(settings.DATA_SOURCE)
    if not connector.test_connection():
        print(f"{C.RED}LOI: Khong ket noi duoc Database!{C.RESET}")
        logger.error("Auto Detect Sensitive: Loi ket noi Database!")
        return False
    print(f"{C.GREEN}OK{C.RESET}")

    # ── BƯỚC 2: Lấy Schema + Profiling (Dữ liệu mẫu) ──
    print(f"{C.YELLOW}[2/4] Doc cau truc Database (Schema + Data Profiling)...{C.RESET}", end=" ")
    engine = SchemaEngine(connector)
    raw_schema = connector.get_schema()
    profiled_schema = engine.profile_columns(raw_schema)
    
    total_columns = sum(len(t["columns"]) for t in profiled_schema)
    print(f"{C.GREEN}OK — {len(profiled_schema)} bang, {total_columns} cot{C.RESET}")

    # ── BƯỚC 3: Chuẩn bị dữ liệu cho AI (AN TOÀN TUYỆT ĐỐI - ZERO DATA LEAK) ──
    schema_text = ""
    for table in profiled_schema:
        t_name = table["table_name"]
        schema_text += f"\n--- Bang: {t_name} ---\n"
        for col in table["columns"]:
            c_name = col["name"]
            c_type = col["type"]
            # CHỈ GỬI TÊN CỘT VÀ KIỂU DỮ LIỆU. BẢO MẬT TUYỆT ĐỐI KHÔNG GỬI DỮ LIỆU MẪU CỦA CÔNG TY RA NGOÀI INTERNET.
            schema_text += f"  - Cot: {c_name} | Kieu: {c_type}\n"

    # ── BƯỚC 4: Gọi AI phân loại ──
    print(f"{C.YELLOW}[3/4] Goi AI phan loai cot nhay cam...{C.RESET}")
    
    prompt = f"""Bạn là một Chuyên gia Bảo mật Dữ liệu (Data Privacy Officer / DPO) lâu năm kinh nghiệm.

## NHIỆM VỤ:
Phân tích cấu trúc Database dưới đây và phân loại TỪNG CỘT vào 1 trong 3 nhóm:

### 3 NHÓM PHÂN LOẠI:
1. "exclude": Cột chứa dữ liệu TUYỆT MẬT mà KHÔNG AI được phép truy vấn qua AI.
   - Ví dụ: Mật khẩu (password, hash), Token xác thực, Mã thẻ tín dụng.
   - Lưu ý: Chỉ những cột mà ngay cả Giám đốc cũng KHÔNG CẦN xem qua AI mới là "exclude".

2. "mask": Cột chứa Thông tin Cá nhân (PII) hoặc Tài chính nhạy cảm nhưng VẪN CẦN cho nghiệp vụ.
   - Ví dụ: Lương (Salary), Số điện thoại (Phone), Email, Số CCCD/CMND (SSN/ID), Địa chỉ nhà.
   - Cột này sẽ được che giấu (masking) tùy quyền hạn người dùng.
   - Với mỗi cột "mask", bạn PHẢI chỉ định kiểu che "mask_type":
     - "full": Che hết (vd: 25000000 -> *********). Dùng cho Lương, CCCD.
     - "partial": Che giữa (vd: 0912345678 -> 091***5678). Dùng cho SĐT, Email.

3. "safe": Cột an toàn. KHÔNG CẦN liệt kê nhóm này.

## QUY TẮC BẮT BUỘC:
- Chỉ liệt kê cột thuộc nhóm "exclude" và "mask".
- Mỗi cột PHẢI có trường "reason" giải thích lý do (tiếng Việt).
- Phân tích DỰA TRÊN tên cột và kiểu dữ liệu (Data Dictionary). Tự suy luận từ tên tiếng Anh của cột.

## ĐỊNH DẠNG OUTPUT (CHỈ TRẢ VỀ JSON, KHÔNG GIẢI THÍCH):
{{
    "exclude": [
        {{"table": "TenBang", "column": "TenCot", "reason": "Ly do cam"}}
    ],
    "mask": [
        {{"table": "TenBang", "column": "TenCot", "reason": "Ly do che", "mask_type": "full hoac partial"}}
    ]
}}

## CẤU TRÚC DATABASE CẦN PHÂN TÍCH:
{schema_text}
"""

    try:
        llm = LLMProvider.get_correction_llm()  # Sử dụng Claude 3.5 Sonnet để output JSON chuẩn xác 100%
        response = llm.invoke(prompt)
        content = response.content.strip()

        # Dùng RegEx bóc khối JSON an toàn
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)

        result = json.loads(content)

        if "exclude" not in result: result["exclude"] = []
        if "mask" not in result: result["mask"] = []

        exclude_count = len(result["exclude"])
        mask_count = len(result["mask"])

        print(f"{C.GREEN}OK — AI da phat hien: {exclude_count} cot CAM + {mask_count} cot CAN CHE{C.RESET}")

        if result["exclude"]:
            print(f"\n{C.RED}{C.BOLD}  COT CAM TUYET DOI (exclude):{C.RESET}")
            for item in result["exclude"]:
                print(f"  {C.RED}  X  {item['table']}.{item['column']} — {item['reason']}{C.RESET}")

        if result["mask"]:
            print(f"\n{C.YELLOW}{C.BOLD}  COT CAN CHE GIAU (mask):{C.RESET}")
            for item in result["mask"]:
                mask_icon = "***" if item.get("mask_type") == "full" else "0**"
                print(f"  {C.YELLOW}  {mask_icon}  {item['table']}.{item['column']} — {item['reason']} [{item.get('mask_type', 'full')}]{C.RESET}")

    except json.JSONDecodeError as e:
        print(f"{C.RED}LOI: AI tra ve JSON khong hop le: {e}{C.RESET}")
        return False
    except Exception as e:
        print(f"{C.RED}LOI: Goi AI that bai: {e}{C.RESET}")
        return False

    # ── BƯỚC 5: Ghi kết quả vào file JSON ──
    print(f"\n{C.YELLOW}[4/4] Ghi ket qua vao {SENSITIVE_CONFIG_PATH}...{C.RESET}", end=" ")
    try:
        with open(SENSITIVE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"{C.GREEN}OK{C.RESET}")
    except Exception as e:
        print(f"{C.RED}LOI: Khong ghi duoc file: {e}{C.RESET}")
        return False

    print(f"\n{C.GREEN}{C.BOLD}{'='*70}{C.RESET}")
    print(f"{C.GREEN}{C.BOLD}  HOAN TAT! Da quet {total_columns} cot va phat hien:{C.RESET}")
    print(f"{C.GREEN}  - {exclude_count} cot CAM TUYET DOI (se bi xoa khoi tri nho AI){C.RESET}")
    print(f"{C.GREEN}  - {mask_count} cot CAN CHE GIAU (se bi mask *** theo quyen han){C.RESET}")
    print(f"{C.GREEN}{C.BOLD}{'='*70}{C.RESET}")
    return True


if __name__ == "__main__":
    detect_sensitive_columns()
