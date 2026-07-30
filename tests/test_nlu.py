"""
TEST NLU ENGINE — Kiểm tra khả năng Phân tích Ý đồ Người dùng
Chạy lệnh: pytest tests/test_nlu.py -v -s
"""
import os
import sys

# Thêm root_dir vào sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv()

# Đảm bảo UTF-8
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

# Schema giả lập (giống cấu trúc DB thật để NLU biết DB có gì)
MOCK_SCHEMA = [
    {
        "table_name": "Fact_Sales",
        "columns": [
            {"name": "SaleID", "type": "integer"},
            {"name": "DateKey", "type": "integer"},
            {"name": "CustomerKey", "type": "integer"},
            {"name": "ProductKey", "type": "integer"},
            {"name": "StoreKey", "type": "integer"},
            {"name": "OrderQuantity", "type": "integer"},
            {"name": "UnitPrice", "type": "numeric"},
            {"name": "DiscountAmount", "type": "numeric"},
            {"name": "SalesAmount", "type": "numeric"},
            {"name": "TaxAmount", "type": "numeric"},
        ]
    },
    {
        "table_name": "Dim_Products",
        "columns": [
            {"name": "ProductKey", "type": "integer"},
            {"name": "ProductID", "type": "varchar"},
            {"name": "ProductName", "type": "varchar"},
            {"name": "Brand", "type": "varchar"},
            {"name": "Category", "type": "varchar"},
            {"name": "SubCategory", "type": "varchar"},
            {"name": "StandardCost", "type": "numeric"},
            {"name": "ListPrice", "type": "numeric"},
        ]
    },
    {
        "table_name": "Dim_Customers",
        "columns": [
            {"name": "CustomerKey", "type": "integer"},
            {"name": "CustomerID", "type": "varchar"},
            {"name": "CustomerName", "type": "varchar"},
            {"name": "CustomerTier", "type": "varchar"},
            {"name": "CreditLimit", "type": "numeric"},
            {"name": "AccountManager", "type": "varchar"},
            {"name": "Region", "type": "varchar"},
            {"name": "City", "type": "varchar"},
        ]
    },
    {
        "table_name": "Dim_Time",
        "columns": [
            {"name": "DateKey", "type": "integer"},
            {"name": "FullDate", "type": "date"},
            {"name": "Year", "type": "integer"},
            {"name": "Quarter", "type": "integer"},
            {"name": "Month", "type": "integer"},
            {"name": "WeekOfYear", "type": "integer"},
            {"name": "DayOfWeek", "type": "varchar"},
            {"name": "IsWeekend", "type": "boolean"},
        ]
    },
    {
        "table_name": "Dim_Stores",
        "columns": [
            {"name": "StoreKey", "type": "integer"},
            {"name": "StoreID", "type": "varchar"},
            {"name": "StoreName", "type": "varchar"},
            {"name": "StoreType", "type": "varchar"},
            {"name": "Region", "type": "varchar"},
            {"name": "ManagerName", "type": "varchar"},
        ]
    },
    {
        "table_name": "Fact_Inventory",
        "columns": [
            {"name": "InventoryID", "type": "integer"},
            {"name": "DateKey", "type": "integer"},
            {"name": "ProductKey", "type": "integer"},
            {"name": "StoreKey", "type": "integer"},
            {"name": "StockOnHand", "type": "integer"},
            {"name": "ReorderPoint", "type": "integer"},
        ]
    }
]

# Danh sách câu hỏi test đa dạng
TEST_QUESTIONS = [
    ("Tổng doanh thu quý 3 là bao nhiêu?",                 "AGGREGATION"),
    ("Top 5 sản phẩm bán chạy nhất",                        "RANKING"),
    ("So sánh doanh thu giữa các vùng miền",                "COMPARISON"),
    ("Xu hướng doanh thu theo tháng năm 2024",              "TREND"),
    ("Liệt kê danh sách khách hàng VIP",                    "DETAIL"),
]


def test_nlu_analyze_intent():
    """Test chính: Kiểm tra NLU có bóc đúng Intent và Entities không."""
    from modules.nlu.engine import NLUEngine

    print(f"\n{C.CYAN}{C.BOLD}{'='*80}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  🧠 TEST NLU ENGINE — PHÂN TÍCH Ý ĐỒ NGƯỜI DÙNG{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'='*80}{C.RESET}\n")

    nlu = NLUEngine()
    passed = 0
    failed = 0

    for question, expected_intent in TEST_QUESTIONS:
        print(f"{C.YELLOW}{'─'*70}{C.RESET}")
        print(f"{C.BOLD}📝 Câu hỏi:{C.RESET} \"{question}\"")
        print(f"{C.DIM}   Intent kỳ vọng: {expected_intent}{C.RESET}")

        result = nlu.analyze_intent(question, schema_columns=MOCK_SCHEMA)

        actual_intent = result.get("intent", "N/A")
        metric = result.get("metric", "N/A")
        dimension = result.get("dimension", "N/A")
        filt = result.get("filter", {})
        time_r = result.get("time_range", {})
        limit = result.get("limit", "N/A")
        sort = result.get("sort", "N/A")

        # Kiểm tra intent
        if actual_intent == expected_intent:
            status = f"{C.GREEN}✅ PASS{C.RESET}"
            passed += 1
        else:
            status = f"{C.RED}❌ FAIL (Got: {actual_intent}){C.RESET}"
            failed += 1

        print(f"   {status}")
        print(f"   {C.MAGENTA}📊 Kết quả NLU:{C.RESET}")
        print(f"      Intent:    {C.BOLD}{actual_intent}{C.RESET}")
        print(f"      Metric:    {metric}")
        print(f"      Dimension: {dimension}")
        print(f"      Filter:    {filt}")
        print(f"      Time:      {time_r}")
        print(f"      Limit:     {limit}")
        print(f"      Sort:      {sort}")

    # Tổng kết
    print(f"\n{C.CYAN}{'='*80}{C.RESET}")
    total = passed + failed
    print(f"{C.BOLD}📊 KẾT QUẢ: {C.GREEN}{passed}/{total} PASSED{C.RESET} | {C.RED}{failed}/{total} FAILED{C.RESET}")
    print(f"{C.CYAN}{'='*80}{C.RESET}\n")

    assert failed == 0, f"NLU Engine có {failed} test case bị sai intent!"


def test_nlu_fallback_on_empty_schema():
    """Test Fallback: NLU vẫn chạy được khi không có schema."""
    from modules.nlu.engine import NLUEngine

    print(f"\n{C.YELLOW}🛡️ TEST FALLBACK: NLU không có Schema...{C.RESET}")

    nlu = NLUEngine()
    result = nlu.analyze_intent("Tổng doanh thu bao nhiêu?", schema_columns=None)

    assert "intent" in result, "Kết quả thiếu field 'intent'!"
    assert result["intent"] in ["AGGREGATION", "GENERAL"], f"Intent không hợp lệ: {result['intent']}"
    assert result["original_question"] == "Tổng doanh thu bao nhiêu?"

    print(f"{C.GREEN}✅ Fallback hoạt động! Intent: {result['intent']}{C.RESET}\n")


if __name__ == "__main__":
    test_nlu_analyze_intent()
    test_nlu_fallback_on_empty_schema()