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