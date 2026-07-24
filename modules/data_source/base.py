from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Dict, Any, Optional

class DataConnector(ABC):
    """
    Abstract Base Class cho tất cả các nguồn dữ liệu.
    Mọi connector (Fabric, PostgreSQL, SQLite) đều phải kế thừa class này.
    Giúp hệ thống có thể đổi nguồn dữ liệu chỉ bằng 1 dòng config trong .env.
    """
    
    @abstractmethod
    def connect(self):
        """Thiết lập kết nối tới database."""
        pass

    @abstractmethod
    def execute(self, sql: str) -> pd.DataFrame:
        """Chạy câu lệnh SQL và trả về DataFrame."""
        pass

    @abstractmethod
    def get_schema(self) -> List[Dict[str, Any]]:
        """Lấy toàn bộ cấu trúc schema (tables + columns) của database."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Kiểm tra xem kết nối có hoạt động không."""
        pass

    @abstractmethod
    def get_dialect(self) -> str:
        """Trả về SQL dialect: 'T-SQL', 'PostgreSQL', hoặc 'SQLite'."""
        pass

    # ═══════════════════════════════════════════════════════════
    # 🔧 BƯỚC 0.5: Các method mới cho Schema Engine (Giai đoạn 3)
    # Mỗi Connector (SQLite, PostgreSQL, Fabric) tự implement
    # theo cách riêng → Schema Engine không phụ thuộc DB cụ thể.
    # ═══════════════════════════════════════════════════════════

    @abstractmethod
    def get_foreign_keys(self) -> List[Dict[str, str]]:
        """
        Quét và trả về danh sách quan hệ Foreign Key giữa các bảng.
        
        Returns:
            List of dicts, mỗi dict có dạng:
            {
                "from_table": "Sales",
                "from_column": "CustomerID",
                "to_table": "Customers",
                "to_column": "CustomerID"
            }
        
        Cách implement tùy từng DB:
            - SQLite:     PRAGMA foreign_key_list(table)
            - PostgreSQL: SELECT ... FROM information_schema.key_column_usage
            - Fabric:     Trả về [] (rỗng) → Schema Engine sẽ dùng Naming Convention
        """
        pass

    @abstractmethod
    def get_sample_values(self, table: str, column: str, limit: int = 50) -> List[Any]:
        """
        Lấy mảng giá trị mẫu DISTINCT của 1 cột (cho Targeted Data Profiling).
        
        Args:
            table:  Tên bảng (ví dụ: "Customers")
            column: Tên cột (ví dụ: "Region")
            limit:  Số lượng giá trị tối đa cần lấy (mặc định 50)
        
        Returns:
            List of distinct values. Ví dụ: ["Miền Bắc", "Miền Nam", "Miền Trung"]
        
        Dùng cho Kỹ thuật RAG #5 (Targeted Data Profiling):
            - Cột < 50 giá trị → Nhét mẫu vào Prompt cho AI.
            - Cột >= 50 giá trị → Bỏ qua (quá nhiều, nổ Prompt).
        """
        pass


def get_connector(source: str) -> DataConnector:
    """
    Factory function: Trả về đúng connector dựa trên giá trị DATA_SOURCE trong .env.
    Ví dụ: DATA_SOURCE=sqlite → SQLiteConnector
           DATA_SOURCE=fabric → FabricConnector
           DATA_SOURCE=postgresql → PostgreSQLConnector
    """
    if source == "fabric":
        from modules.data_source.fabric import FabricConnector
        return FabricConnector() 
    elif source == "postgresql":
        from modules.data_source.postgresql import PostgreSQLConnector
        return PostgreSQLConnector()
    elif source == "sqlite":
        from modules.data_source.sqlite_source import SQLiteConnector
        return SQLiteConnector()
    else:
        raise ValueError(f"DATA_SOURCE không hợp lệ: '{source}'. Chỉ hỗ trợ: fabric, postgresql, sqlite")