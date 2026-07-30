"""
TEST SQL VALIDATOR — Kiểm tra Cảnh sát SQL
Chạy lệnh: python tests/test_sql_validator.py
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

class C:
    CYAN = '\033[96m'; GREEN = '\033[92m'; YELLOW = '\033[93m'
    RED = '\033[91m'; BOLD = '\033[1m'; RESET = '\033[0m'; DIM = '\033[2m'


def test_sql_validator():
    from modules.sql.validator import SQLValidator

    print(f"\n{C.CYAN}{C.BOLD}{'='*80}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  🛡️ TEST SQL VALIDATOR — CẢNH SÁT KIỂM ĐỊNH SQL{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'='*80}{C.RESET}\n")

    v = SQLValidator()
    passed = 0
    failed = 0

    tests = [
        # === SYNTAX ===
        ("Cú pháp: SQL SELECT hợp lệ",
         'SELECT SUM("SalesAmount") FROM "Fact_Sales"',
         True, "syntax"),

        ("Cú pháp: Chặn DELETE",
         'DELETE FROM "Fact_Sales" WHERE 1=1',
         False, "syntax"),

        ("Cú pháp: Chặn DROP TABLE",
         'DROP TABLE "Fact_Sales"',
         False, "syntax"),

        ("Cú pháp: Chặn INSERT",
         'INSERT INTO "Fact_Sales" VALUES (1, 2, 3)',
         False, "syntax"),

        ("Cú pháp: Chặn SQL Injection (nhiều lệnh ghép)",
         'SELECT * FROM "Fact_Sales"; DROP TABLE "Fact_Sales"',
         False, "syntax"),

        ("Cú pháp: Cho phép WITH (CTE)",
         'WITH cte AS (SELECT * FROM "Fact_Sales") SELECT * FROM cte',
         True, "syntax"),

        ("Cú pháp: SQL rỗng",
         '',
         False, "syntax"),

        # === QUERY LIMIT ===
        ("Limit: Tự thêm LIMIT cho SELECT *",
         'SELECT * FROM "Dim_Customers"',
         None, "limit"),

        ("Limit: Không thêm LIMIT cho SUM (1 dòng)",
         'SELECT SUM("SalesAmount") FROM "Fact_Sales"',
         None, "limit_no_change"),

        ("Limit: Giữ nguyên LIMIT đã có",
         'SELECT * FROM "Dim_Customers" LIMIT 50',
         None, "limit_keep"),
    ]

    for name, sql, expect_valid, test_type in tests:
        print(f"{C.YELLOW}{'─'*60}{C.RESET}")
        print(f"{C.BOLD}📝 {name}{C.RESET}")
        print(f"{C.DIM}   SQL: {sql[:80]}{'...' if len(sql) > 80 else ''}{C.RESET}")

        if test_type == "syntax":
            result = v.validate_syntax(sql)
            is_pass = result["valid"] == expect_valid
            if is_pass:
                print(f"   {C.GREEN}✅ PASS — valid={result['valid']}{C.RESET}")
                passed += 1
            else:
                print(f"   {C.RED}❌ FAIL — Expect valid={expect_valid}, Got {result['valid']}{C.RESET}")
                failed += 1
            if result["error"]:
                print(f"   {C.DIM}   Lý do: {result['error']}{C.RESET}")

        elif test_type == "limit":
            result_sql = v.enforce_query_limit(sql)
            has_limit = "LIMIT" in result_sql.upper()
            if has_limit:
                print(f"   {C.GREEN}✅ PASS — Đã tự thêm LIMIT{C.RESET}")
                print(f"   {C.DIM}   → {result_sql.strip()}{C.RESET}")
                passed += 1
            else:
                print(f"   {C.RED}❌ FAIL — Không thêm LIMIT{C.RESET}")
                failed += 1

        elif test_type == "limit_no_change":
            result_sql = v.enforce_query_limit(sql)
            no_limit = "LIMIT" not in result_sql.upper()
            if no_limit:
                print(f"   {C.GREEN}✅ PASS — Đúng, SUM không cần LIMIT{C.RESET}")
                passed += 1
            else:
                print(f"   {C.RED}❌ FAIL — Thêm LIMIT thừa cho SUM{C.RESET}")
                failed += 1

        elif test_type == "limit_keep":
            result_sql = v.enforce_query_limit(sql)
            kept_original = "LIMIT 50" in result_sql.upper()
            if kept_original:
                print(f"   {C.GREEN}✅ PASS — Giữ nguyên LIMIT 50 gốc{C.RESET}")
                passed += 1
            else:
                print(f"   {C.RED}❌ FAIL — Đã sửa LIMIT gốc{C.RESET}")
                failed += 1

    # Tổng kết
    print(f"\n{C.CYAN}{'='*80}{C.RESET}")
    total = passed + failed
    print(f"{C.BOLD}📊 KẾT QUẢ: {C.GREEN}{passed}/{total} PASSED{C.RESET} | {C.RED}{failed}/{total} FAILED{C.RESET}")
    print(f"{C.CYAN}{'='*80}{C.RESET}\n")


if __name__ == "__main__":
    test_sql_validator()