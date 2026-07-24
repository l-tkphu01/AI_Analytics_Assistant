import pandas as pd
import time
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pandas")
from typing import List, Dict, Any
from modules.data_source.base import DataConnector
from config.settings import settings
from core.logger import get_logger
from core.exceptions import DatabaseConnectionError

logger = get_logger(__name__)


class PostgreSQLConnector(DataConnector):
    """
    Connector cho PostgreSQL / Supabase.
    Dùng khi: Fabric trial hết hạn, hoặc muốn test với Supabase Free (500MB).
    """

    def __init__(self): 
        self._connection = None

    def connect(self):
        """Kết nối tới PostgreSQL."""
        try:
            import psycopg2

            self._connection = psycopg2.connect(settings.DATABASE_URL)
            logger.info("Đã kết nối PostgreSQL")
            return self._connection

        except ImportError:
            raise DatabaseConnectionError("Chưa cài thư viện psycopg2. Chạy: pip install psycopg2-binary")
        except Exception as e:
            raise DatabaseConnectionError(f"Không thể kết nối PostgreSQL: {e}")

    def execute(self, sql: str) -> pd.DataFrame:
        """Chạy SQL trên PostgreSQL."""
        if not self._connection:
            self.connect()

        start_time = time.time()
        try:
            df = pd.read_sql_query(sql, self._connection)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"PostgreSQL query OK: {len(df)} rows, {elapsed:.0f}ms")
            return df
        except Exception as e:
            logger.error(f"PostgreSQL query lỗi: {e}")
            raise

    def get_schema(self) -> List[Dict[str, Any]]:
        """Đọc schema từ PostgreSQL information_schema."""
        if not self._connection:
            self.connect()

        tables_sql = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        tables_df = pd.read_sql_query(tables_sql, self._connection)

        schema = []
        for _, row in tables_df.iterrows():
            table_name = row["table_name"]

            cols_sql = f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position
            """
            cols_df = pd.read_sql_query(cols_sql, self._connection)

            columns = []
            for _, col_row in cols_df.iterrows():
                columns.append({
                    "name": col_row["column_name"],
                    "type": col_row["data_type"],
                    "nullable": col_row["is_nullable"] == "YES",
                    "primary_key": False
                })

            schema.append({
                "table_name": table_name,
                "columns": columns,
                "row_count": -1
            })

        logger.info(f"PostgreSQL schema: {len(schema)} tables")
        return schema

    def test_connection(self) -> bool:
        try:
            if not self._connection:
                self.connect()
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_dialect(self) -> str:
        return "PostgreSQL"

    def get_foreign_keys(self) -> list:
        """
        Quét Foreign Key từ information_schema trong PostgreSQL.
        """
        if not self._connection:
            self.connect()

        fk_sql = """
            SELECT
                kcu.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public';
        """
        try:
            df = pd.read_sql_query(fk_sql, self._connection)
            foreign_keys = df.to_dict(orient="records")
            logger.info(f"PostgreSQL FK: {len(foreign_keys)} quan hệ")
            return foreign_keys
        except Exception as e:
            logger.warning(f"Lỗi quét FK PostgreSQL: {e}")
            return []

    def get_sample_values(self, table: str, column: str, limit: int = 50) -> list:
        """
        Lấy giá trị mẫu DISTINCT trong PostgreSQL.
        """
        if not self._connection:
            self.connect()

        try:
            sql = f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL LIMIT {limit}'
            df = pd.read_sql_query(sql, self._connection)
            values = df[column].dropna().tolist()
            logger.info(f"PostgreSQL Data Profiling [{table}.{column}]: {len(values)} giá trị")
            return values
        except Exception as e:
            logger.warning(f"Không thể lấy mẫu PostgreSQL [{table}.{column}]: {e}")
            return []

    def close(self):
        if self._connection:
            self._connection.close()
            self._connection = None