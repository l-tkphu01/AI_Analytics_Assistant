import sqlite3
import pandas as pd
import os
import time
from typing import List, Dict, Any
from modules.data_source.base import DataConnector
from core.logger import get_logger

logger = get_logger(__name__)

# Đường dẫn mặc định tới file SQLite dùng để test/demo
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "analytics.db")


class SQLiteConnector(DataConnector):
    """
    Connector cho SQLite — dùng trong các trường hợp:
    1. Phát triển local (không cần Internet)
    2. Chạy test tự động (pytest)
    3. Demo offline khi trình bày đồ án
    4. Fallback khi Fabric trial hết hạn
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.abspath(DEFAULT_DB_PATH)
        self._connection = None

    def connect(self):
        """Tạo kết nối tới file SQLite."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # SỬA Ở ĐÂY: Thêm check_same_thread=False 
        self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        logger.info(f"Đã kết nối SQLite tại: {self.db_path}")
        return self._connection

    def execute(self, sql: str) -> pd.DataFrame:
        """Chạy SQL và trả về kết quả dạng DataFrame."""
        if not self._connection:
            self.connect()

        start_time = time.time()
        try:
            df = pd.read_sql_query(sql, self._connection)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Query thành công: {len(df)} rows, {elapsed:.0f}ms")
            return df
        except Exception as e:
            logger.error(f"Lỗi khi chạy SQL: {e}")
            raise

    def get_schema(self) -> List[Dict[str, Any]]:
        """Đọc cấu trúc tất cả các bảng trong SQLite."""
        if not self._connection:
            self.connect()

        cursor = self._connection.cursor()

        # Lấy danh sách tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        schema = []
        for table_name in tables:
            # Lấy thông tin columns của từng table
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            columns = []
            for col in cursor.fetchall():
                columns.append({
                    "name": col[1],
                    "type": col[2],
                    "nullable": not col[3],  # notnull flag
                    "primary_key": bool(col[5])
                })

            # Đếm số dòng trong bảng
            cursor.execute(f"SELECT COUNT(*) FROM '{table_name}'")
            row_count = cursor.fetchone()[0]

            schema.append({
                "table_name": table_name,
                "columns": columns,
                "row_count": row_count
            })

        logger.info(f"Đã đọc schema: {len(schema)} tables")
        return schema

    def test_connection(self) -> bool:
        """Kiểm tra kết nối SQLite."""
        try:
            if not self._connection:
                self.connect()
            self._connection.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_dialect(self) -> str:
        return "SQLite"

    # ═══════════════════════════════════════════════════════════
    # 🔧 BƯỚC 0.5: Implement cho SQLite (Giai đoạn 3)
    # ═══════════════════════════════════════════════════════════

    def get_foreign_keys(self) -> list:
        """
        Quét Foreign Key từ metadata SQLite bằng PRAGMA foreign_key_list.
        Trả về danh sách dict chuẩn hóa để Schema Engine dùng.
        """
        if not self._connection:
            self.connect()

        cursor = self._connection.cursor()

        # Lấy danh sách tất cả các bảng
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        foreign_keys = []
        for table_name in tables:
            cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
            for fk in cursor.fetchall():
                # PRAGMA foreign_key_list trả về:
                # (id, seq, to_table, from_column, to_column, on_update, on_delete, match)
                foreign_keys.append({
                    "from_table": table_name,
                    "from_column": fk[3],   # Cột ở bảng hiện tại
                    "to_table": fk[2],      # Bảng đích
                    "to_column": fk[4],     # Cột ở bảng đích
                })

        logger.info(f"Đã quét FK: {len(foreign_keys)} quan hệ từ {len(tables)} bảng")
        return foreign_keys

    def get_sample_values(self, table: str, column: str, limit: int = 50) -> list:
        """
        Lấy giá trị mẫu DISTINCT của 1 cột trong SQLite.
        Dùng cho Kỹ thuật RAG #5 (Targeted Data Profiling).
        """
        if not self._connection:
            self.connect()

        try:
            cursor = self._connection.cursor()
            # Dùng DISTINCT để lấy giá trị không trùng, LIMIT để giới hạn
            cursor.execute(f"SELECT DISTINCT \"{column}\" FROM \"{table}\" WHERE \"{column}\" IS NOT NULL LIMIT ?", (limit,))
            values = [row[0] for row in cursor.fetchall()]
            logger.info(f"Data Profiling [{table}.{column}]: {len(values)} giá trị distinct")
            return values
        except Exception as e:
            logger.warning(f"Không thể lấy mẫu [{table}.{column}]: {e}")
            return []

    def close(self):
        """Đóng kết nối."""
        if self._connection:
            self._connection.close()
            self._connection = None


def create_sample_data(db_path: str = None):
    """
    Tạo dữ liệu mẫu (Sales + Customers + Products) để test hệ thống.
    Chạy 1 lần duy nhất khi chưa có data.
    """
    connector = SQLiteConnector(db_path)
    conn = connector.connect()
    cursor = conn.cursor()

    # ═══ Bảng Customers ═══
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Customers (
            CustomerID INTEGER PRIMARY KEY,
            CustomerName TEXT NOT NULL,
            Region TEXT NOT NULL,
            City TEXT,
            Segment TEXT
        )
    """)

    customers_data = [
        (1, "Công ty TNHH ABC",    "Miền Bắc",  "Hà Nội",      "Doanh nghiệp"),
        (2, "Cửa hàng XYZ",        "Miền Nam",   "TP.HCM",      "Bán lẻ"),
        (3, "Tập đoàn DEF",        "Miền Bắc",   "Hải Phòng",   "Doanh nghiệp"),
        (4, "Shop Online GHI",     "Miền Trung", "Đà Nẵng",     "Bán lẻ"),
        (5, "Đại lý JKL",          "Miền Nam",   "Cần Thơ",     "Đại lý"),
        (6, "Siêu thị MNO",        "Miền Bắc",   "Hà Nội",      "Bán lẻ"),
        (7, "Công ty PQR",         "Miền Trung", "Huế",          "Doanh nghiệp"),
        (8, "Chuỗi STU",           "Miền Nam",   "TP.HCM",      "Bán lẻ"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO Customers VALUES (?, ?, ?, ?, ?)", customers_data)

    # ═══ Bảng Products ═══
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Products (
            ProductID INTEGER PRIMARY KEY,
            ProductName TEXT NOT NULL,
            Category TEXT NOT NULL,
            UnitPrice REAL NOT NULL
        )
    """)

    products_data = [
        (1, "Laptop Dell XPS 15",     "Điện tử",       25000000),
        (2, "iPhone 15 Pro Max",      "Điện thoại",     32000000),
        (3, "Bàn phím cơ Keychron",   "Phụ kiện",       2500000),
        (4, "Màn hình LG 27 inch",    "Điện tử",       8000000),
        (5, "Tai nghe Sony WH-1000",  "Phụ kiện",       7500000),
        (6, "iPad Air M2",            "Máy tính bảng",  18000000),
        (7, "Chuột Logitech MX",      "Phụ kiện",       1800000),
        (8, "Samsung Galaxy S24",     "Điện thoại",     27000000),
    ]
    cursor.executemany("INSERT OR IGNORE INTO Products VALUES (?, ?, ?, ?)", products_data)

    # ═══ Bảng Sales (Doanh thu) ═══
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Sales (
            SaleID INTEGER PRIMARY KEY,
            OrderDate TEXT NOT NULL,
            CustomerID INTEGER,
            ProductID INTEGER,
            Quantity INTEGER NOT NULL,
            Revenue REAL NOT NULL,
            Cost REAL NOT NULL,
            Profit REAL NOT NULL,
            Region TEXT NOT NULL,
            FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
            FOREIGN KEY (ProductID) REFERENCES Products(ProductID)
        )
    """)

    sales_data = [
        # Tháng 1/2025
        (1,  "2025-01-05", 1, 1, 3,  75000000,  60000000,  15000000, "Miền Bắc"),
        (2,  "2025-01-12", 2, 2, 5,  160000000, 128000000, 32000000, "Miền Nam"),
        (3,  "2025-01-20", 3, 3, 10, 25000000,  18000000,  7000000,  "Miền Bắc"),
        # Tháng 2/2025
        (4,  "2025-02-03", 4, 4, 4,  32000000,  24000000,  8000000,  "Miền Trung"),
        (5,  "2025-02-14", 5, 5, 6,  45000000,  33000000,  12000000, "Miền Nam"),
        (6,  "2025-02-28", 6, 6, 2,  36000000,  28000000,  8000000,  "Miền Bắc"),
        # Tháng 3/2025
        (7,  "2025-03-10", 7, 7, 15, 27000000,  19500000,  7500000,  "Miền Trung"),
        (8,  "2025-03-22", 8, 8, 3,  81000000,  63000000,  18000000, "Miền Nam"),
        (9,  "2025-03-31", 1, 1, 2,  50000000,  40000000,  10000000, "Miền Bắc"),
        # Tháng 4/2025
        (10, "2025-04-05", 2, 2, 4,  128000000, 100000000, 28000000, "Miền Nam"),
        (11, "2025-04-15", 3, 4, 5,  40000000,  30000000,  10000000, "Miền Bắc"),
        (12, "2025-04-25", 4, 6, 3,  54000000,  42000000,  12000000, "Miền Trung"),
        # Tháng 5/2025
        (13, "2025-05-08", 5, 8, 6,  162000000, 126000000, 36000000, "Miền Nam"),
        (14, "2025-05-18", 6, 3, 20, 50000000,  36000000,  14000000, "Miền Bắc"),
        (15, "2025-05-30", 7, 5, 8,  60000000,  44000000,  16000000, "Miền Trung"),
        # Tháng 6/2025
        (16, "2025-06-10", 8, 1, 5,  125000000, 100000000, 25000000, "Miền Nam"),
        (17, "2025-06-20", 1, 7, 12, 21600000,  15600000,  6000000,  "Miền Bắc"),
        (18, "2025-06-28", 2, 2, 7,  224000000, 175000000, 49000000, "Miền Nam"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO Sales VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sales_data)

    conn.commit()
    logger.info("Đã tạo dữ liệu mẫu: Customers (8), Products (8), Sales (18)")
    return connector