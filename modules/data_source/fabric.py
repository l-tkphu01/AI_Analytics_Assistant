import pandas as pd
import time
from typing import List, Dict, Any
from modules.data_source.base import DataConnector
from config.settings import settings
from core.logger import get_logger
from core.exceptions import DatabaseConnectionError

logger = get_logger(__name__)


class FabricConnector(DataConnector):
    """
    Connector cho Microsoft Fabric SQL Endpoint.
    Sử dụng pyodbc + ODBC Driver 18 + Service Principal authentication.
    """

    def __init__(self):
        self._connection = None

    def connect(self):
        """Kết nối tới Fabric SQL Endpoint qua pyodbc."""
        try:
            import pyodbc

            connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={settings.FABRIC_SQL_ENDPOINT};"
                f"DATABASE={settings.FABRIC_DATABASE};"
                f"UID={settings.FABRIC_CLIENT_ID};"
                f"PWD={settings.FABRIC_CLIENT_SECRET};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
            self._connection = pyodbc.connect(connection_string)
            logger.info(f"Đã kết nối Fabric: {settings.FABRIC_SQL_ENDPOINT}")
            return self._connection

        except ImportError:
            raise DatabaseConnectionError("Chưa cài thư viện pyodbc. Chạy: pip install pyodbc")
        except Exception as e:
            raise DatabaseConnectionError(f"Không thể kết nối Fabric: {e}")

    def execute(self, sql: str) -> pd.DataFrame:
        """Chạy SQL trên Fabric và trả về DataFrame."""
        if not self._connection:
            self.connect()

        start_time = time.time()
        try:
            df = pd.read_sql_query(sql, self._connection)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Fabric query OK: {len(df)} rows, {elapsed:.0f}ms")
            return df
        except Exception as e:
            logger.error(f"Fabric query lỗi: {e}")
            raise

    def get_schema(self) -> List[Dict[str, Any]]:
        """Đọc cấu trúc schema từ Fabric INFORMATION_SCHEMA."""
        if not self._connection:
            self.connect()

        # Lấy danh sách tables
        tables_sql = """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """
        tables_df = pd.read_sql_query(tables_sql, self._connection)

        schema = []
        for _, row in tables_df.iterrows():
            table_name = row["TABLE_NAME"]

            # Lấy columns cho mỗi table
            cols_sql = f"""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '{table_name}'
                ORDER BY ORDINAL_POSITION
            """
            cols_df = pd.read_sql_query(cols_sql, self._connection)

            columns = []
            for _, col_row in cols_df.iterrows():
                columns.append({
                    "name": col_row["COLUMN_NAME"],
                    "type": col_row["DATA_TYPE"],
                    "nullable": col_row["IS_NULLABLE"] == "YES",
                    "primary_key": False
                })

            schema.append({
                "table_name": table_name,
                "columns": columns,
                "row_count": -1  # Không đếm rows trên Fabric (tốn tài nguyên)
            })

        logger.info(f"Fabric schema: {len(schema)} tables")
        return schema

    def test_connection(self) -> bool:
        """Kiểm tra kết nối Fabric."""
        try:
            if not self._connection:
                self.connect()
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_dialect(self) -> str:
        return "T-SQL"

    def get_foreign_keys(self) -> list:
        """
        Fabric Data Warehouse không lưu Foreign Key vật lý.
        Trả về [] (rỗng) → Schema Engine sẽ dùng Naming Convention & file JSON.
        """
        logger.info("Fabric không có FK vật lý. Trả về [] để dùng Naming Convention.")
        return []

    def get_sample_values(self, table: str, column: str, limit: int = 50) -> list:
        """
        Lấy giá trị mẫu DISTINCT trong Fabric (T-SQL dùng TOP).
        """
        if not self._connection:
            self.connect()

        try:
            sql = f"SELECT DISTINCT TOP {limit} [{column}] FROM [{table}] WHERE [{column}] IS NOT NULL"
            df = pd.read_sql_query(sql, self._connection)
            values = df[column].dropna().tolist()
            logger.info(f"Fabric Data Profiling [{table}.{column}]: {len(values)} giá trị")
            return values
        except Exception as e:
            logger.warning(f"Không thể lấy mẫu Fabric [{table}.{column}]: {e}")
            return []

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None