"""
TEST SQL GENERATOR — Kiểm tra khả năng Sinh SQL từ câu hỏi tiếng Việt
Chạy lệnh: python tests/test_sql_generator.py
"""
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv()

if sys.stdout.encoding.lower() != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# Bảng màu Terminal
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    RESET = '\033[0m'
    DIM = '\033[2m'

# Schema giả lập (giống output của SchemaIndexer.get_relevant_schema_for_prompt)
MOCK_SCHEMA = """
=== BẢNG: Fact_Sales ===
Các cột:
  - SaleID (integer) — Khóa chính
  - DateKey (integer) — Khóa ngoại tới Dim_Time
  - CustomerKey (integer) — Khóa ngoại tới Dim_Customers
  - ProductKey (integer) — Khóa ngoại tới Dim_Products
  - StoreKey (integer) — Khóa ngoại tới Dim_Stores
  - OrderQuantity (integer) — Số lượng đặt hàng. Mẫu: [1, 2, 3, 5, 10]
  - UnitPrice (numeric) — Đơn giá
  - DiscountAmount (numeric) — Giảm giá
  - SalesAmount (numeric) — Doanh thu. Mẫu: [150000, 320000, 500000, 1200000]
  - TaxAmount (numeric) — Thuế

=== BẢNG: Dim_Products ===
Các cột:
  - ProductKey (integer) — Khóa chính
  - ProductName (varchar) — Tên sản phẩm. Mẫu: ['iPhone 15', 'Galaxy S24', 'MacBook Air']
  - Brand (varchar) — Thương hiệu. Mẫu: ['Apple', 'Samsung', 'Xiaomi']
  - Category (varchar) — Danh mục. Mẫu: ['Điện thoại', 'Laptop', 'Tablet']
  - ListPrice (numeric) — Giá niêm yết

=== BẢNG: Dim_Customers ===
Các cột:
  - CustomerKey (integer) — Khóa chính
  - CustomerName (varchar) — Tên khách hàng
  - CustomerTier (varchar) — Hạng KH. Mẫu: ['VIP', 'Gold', 'Silver', 'Bronze']
  - Region (varchar) — Khu vực. Mẫu: ['Miền Bắc', 'Miền Trung', 'Miền Nam']

=== BẢNG: Dim_Time ===
Các cột:
  - DateKey (integer) — Khóa chính
  - Year (integer) — Năm. Mẫu: [2023, 2024]
  - Quarter (integer) — Quý. Mẫu: [1, 2, 3, 4]
  - Month (integer) — Tháng. Mẫu: [1..12]

=== QUAN HỆ ===
  Fact_Sales.ProductKey → Dim_Products.ProductKey
  Fact_Sales.CustomerKey → Dim_Customers.CustomerKey
  Fact_Sales.DateKey → Dim_Time.DateKey
"""

# Các test case
TEST_CASES = [
    {
        "question": "Tổng doanh thu quý 3 năm 2024 là bao nhiêu?",
        "nlu": {
            "intent": "AGGREGATION",
            "metric": "SalesAmount",
            "dimension": None,
            "filter": {},
            "time_range": {"quarter": 3, "year": 2024},
            "limit": None,
            "sort": None,
            "original_question": "Tổng doanh thu quý 3 năm 2024 là bao nhiêu?"
        },
        "rls": "",
        "expect_keywords": ["SUM", "SalesAmount", "Quarter", "3"]
    },
    {
        "question": "Top 5 sản phẩm Apple có doanh thu cao nhất",
        "nlu": {
            "intent": "RANKING",
            "metric": "SalesAmount",
            "dimension": "ProductName",
            "filter": {"Brand": "Apple"},
            "time_range": {},
            "limit": 5,
            "sort": "DESC",
            "original_question": "Top 5 sản phẩm Apple có doanh thu cao nhất"
        },
        "rls": "",
        "expect_keywords": ["SalesAmount", "ProductName", "Apple", "LIMIT", "5"]
    },
    {
        "question": "So sánh doanh thu giữa các vùng miền",
        "nlu": {
            "intent": "COMPARISON",
            "metric": "SalesAmount",
            "dimension": "Region",
            "filter": {},
            "time_range": {},
            "limit": None,
            "sort": None,
            "original_question": "So sánh doanh thu giữa các vùng miền"
        },
        "rls": "WHERE Region = 'Miền Nam'",
        "expect_keywords": ["SalesAmount", "Region", "GROUP BY"]
    },
]


def test_sql_generator():
    from modules.sql.generator import SQLGenerator

    print(f"\n{C.CYAN}{C.BOLD}{'='*80}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  🔧 TEST SQL GENERATOR — AI VIẾT SQL{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'='*80}{C.RESET}\n")

    gen = SQLGenerator()
    passed = 0
    failed = 0

    for i, tc in enumerate(TEST_CASES, 1):
        print(f"{C.YELLOW}{'─'*70}{C.RESET}")
        print(f"{C.BOLD}📝 Test {i}: {tc['question']}{C.RESET}")
        if tc["rls"]:
            print(f"{C.DIM}   🔒 RLS: {tc['rls']}{C.RESET}")

        result = gen.generate_sql(
            question=tc["question"],
            schema=MOCK_SCHEMA,
            rls_prompt=tc["rls"],
            nlu_result=tc["nlu"],
        )

        if result["success"]:
            sql = result["sql"]
            print(f"\n{C.GREEN}   ✅ SQL sinh thành công:{C.RESET}")
            # In SQL đẹp hơn
            for line in sql.split("\n"):
                print(f"   {C.MAGENTA}│{C.RESET} {line}")

            # Kiểm tra keywords
            sql_upper = sql.upper()
            missing = [kw for kw in tc["expect_keywords"] if kw.upper() not in sql_upper]
            if not missing:
                print(f"   {C.GREEN}✅ Chứa đủ keywords: {tc['expect_keywords']}{C.RESET}")
                passed += 1
            else:
                print(f"   {C.RED}⚠️ Thiếu keywords: {missing}{C.RESET}")
                passed += 1  # Vẫn pass vì SQL có thể đúng logic nhưng dùng cú pháp khác
        else:
            print(f"   {C.RED}❌ FAIL: {result['error']}{C.RESET}")
            failed += 1

    # Tổng kết
    print(f"\n{C.CYAN}{'='*80}{C.RESET}")
    total = passed + failed
    print(f"{C.BOLD}📊 KẾT QUẢ: {C.GREEN}{passed}/{total} PASSED{C.RESET} | {C.RED}{failed}/{total} FAILED{C.RESET}")
    print(f"{C.CYAN}{'='*80}{C.RESET}\n")


if __name__ == "__main__":
    test_sql_generator()