import os
import json
import pandas as pd
from core.models import UserContext
from core.logger import get_logger

logger = get_logger(__name__)

class CLSManager:
    """
    Column-Level Security (CLS) Manager.
    Chịu trách nhiệm che giấu hoặc xóa bỏ các cột dữ liệu nhạy cảm
    TRƯỚC KHI kết quả được trả về cho người dùng, dựa trên Role.
    """
    def __init__(self, config_path: str = None):
        if config_path is None:
            # Đường dẫn mặc định tới config/sensitive_columns.json
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, "..", "..", "config", "sensitive_columns.json")
             
        self.config_path = os.path.normpath(config_path)
        self.exclude_columns = []
        self.mask_columns = {}  # format: {"ColumnName": "mask_type"}
        self._load_config()
        
        # [Singleton] Lưu instance đầu tiên để các module khác dùng lại
        CLSManager._instance = self

    def _load_config(self):
        """Đọc danh sách cột nhạy cảm từ file JSON do AI sinh ra."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"CLS: Không tìm thấy file {self.config_path}. Bỏ qua CLS.")
                return

            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Lấy list các cột cấm (exclude)
            for item in data.get("exclude", []):
                # Lưu dưới dạng lowercase để so sánh không phân biệt hoa thường
                self.exclude_columns.append(item.get("column", "").lower())

            # Lấy danh sách các cột cần che (mask)
            for item in data.get("mask", []):
                col = item.get("column", "").lower()
                m_type = item.get("mask_type", "full")
                self.mask_columns[col] = m_type

            logger.info(f"CLS: Đã nạp {len(self.exclude_columns)} cột cấm, {len(self.mask_columns)} cột cần che.")

        except Exception as e:
            logger.error(f"CLS: Lỗi khi nạp file cấu hình: {e}")

    def apply_masking(self, df: pd.DataFrame, user: UserContext) -> pd.DataFrame:
        """
        Thực thi che giấu dữ liệu trên DataFrame.
        """
        if df is None or df.empty:
            return df
            
        # 1. Kiểm tra Quyền Miễn trừ (Bypass)
        # Giám đốc (admin) có CLS_Bypass = True thì xem Full không bị che
        cls_bypass = user.attributes.get("CLS_Bypass", False)
        if cls_bypass:
            logger.debug(f"CLS: User {user.username} có quyền CLS_Bypass. Không che dữ liệu.")
            return df
            
        logger.debug(f"CLS: Đang kiểm duyệt dữ liệu cho User {user.username}...")
        
        df_masked = df.copy()
        
        # DataFrame columns in lower case for matching
        df_cols_lower = [str(c).lower() for c in df_masked.columns]
        
        # Tạo danh sách các cột bị xóa để không bị lỗi index khi duyệt
        cols_to_drop = []
        
        for idx, col_lower in enumerate(df_cols_lower):
            real_col_name = df_masked.columns[idx]
            
            # 2. Xóa cột Cấm Tuyệt Đối (Exclude)
            # Dù có lỡ query ra (do hacker injection), cũng bị xóa sạch trước khi hiển thị
            if col_lower in self.exclude_columns:
                logger.warning(f"CLS: Đã XÓA cột cấm [{real_col_name}] khỏi kết quả.")
                cols_to_drop.append(real_col_name)
                continue
                
            # 3. Che cột Nhạy Cảm (Mask)
            if col_lower in self.mask_columns:
                mask_type = self.mask_columns[col_lower]
                logger.info(f"CLS: Đang che cột [{real_col_name}] với kiểu {mask_type}.")
                
                if mask_type == "full":
                    # Che toàn bộ bằng ***
                    df_masked[real_col_name] = "***"
                elif mask_type == "partial":
                    # Che một phần
                    def partial_mask(val):
                        if pd.isna(val) or val is None:
                            return val
                        s = str(val)
                        if len(s) <= 4:
                            return "***"
                        # Giữ 3 ký tự đầu, 1 ký tự cuối. Giữa che ***
                        return f"{s[:3]}***{s[-1]}"
                        
                    df_masked[real_col_name] = df_masked[real_col_name].apply(partial_mask)

        if cols_to_drop:
            df_masked.drop(columns=cols_to_drop, inplace=True)
            
        return df_masked