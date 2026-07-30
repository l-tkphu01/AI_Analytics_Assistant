"""
TEST SELF-CORRECTION — Kiểm tra AI Tự Sửa SQL
Chạy lệnh: python tests/test_self_correction.py
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

import pandas as pd
from modules.sql.self_correction import SelfCorrection

class C:
    CYAN = '\033[96m'; GREEN = '\033[92m'; YELLOW = '\033[93m'
    RED = '\033[91m'; BOLD = '\033[1m'; RESET = '\033[0m'; DIM = '\033[2m'


# ============================================================
# MOCK CONNECTOR: Giả lập DB để test mà không cần PostgreSQL thật
# ============================================================
class MockConnector:
    """
    Giả lập DB: 
    - Lần 1: Ném lỗi (giả SQL sai)
    - Lần 2: Trả kết quả (giả AI đã sửa đúng)
    """
    def __init__(self):
        self.call_count = 0
        self.queries_received = []

    def execute(self, sql: str) -> pd.DataFrame:
        self.call_count += 1
        self.queries_received.append(sql)

        if self.call_count == 1:
            # Lần 1: Giả lập SQL lỗi
            raise Exception('relation "fact_salez" does not exist')
        else:
            # Lần 2+: Giả lập chạy thành công
            return pd.DataFrame({
                "total": [1500000],
            })


class MockConnectorAlwaysFail:
    """Giả lập DB luôn lỗi (test max retry)."""
    def execute(self, sql: str) -> pd.DataFrame:
        raise Exception('syntax error at or near "SELECCT"')


def test_self_correction():
    print(f"\n{C.CYAN}{C.BOLD}{'='*80}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}  🔧 TEST SELF-CORRECTION — AI TỰ SỬA SQL{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'='*80}{C.RESET}\n")

    passed = 0
    failed = 0

    # ── TEST 1: SQL lỗi lần 1, AI sửa, lần 2 thành công ──
    print(f"{C.YELLOW}{'─'*60}{C.RESET}")
    print(f"{C.BOLD}📝 Test 1: SQL lỗi → AI sửa → Thành công ở lần 2{C.RESET}")

    mock_db = MockConnector()
    sc = SelfCorrection(connector=mock_db)

    result = sc.execute_with_retry(
        sql='SELECT SUM("SalesAmount") FROM "fact_salez"',  # Sai tên bảng!
        schema='Bảng: Fact_Sales (cột: SalesAmount)',
        max_retries=3,
    )

    if result["success"]:
        print(f"   {C.GREEN}✅ PASS — Thành công sau {result['retries']} lần retry!{C.RESET}")
        print(f"   {C.DIM}   Data: {result['data'].to_dict()}{C.RESET}")
        print(f"   {C.DIM}   SQL cuối: {result['sql_final'][:80]}{C.RESET}")
        passed += 1
    else:
        print(f"   {C.RED}❌ FAIL — {result['error']}{C.RESET}")
        failed += 1

    # ── TEST 2: SQL luôn lỗi → Bó tay sau max_retries ──
    print(f"\n{C.YELLOW}{'─'*60}{C.RESET}")
    print(f"{C.BOLD}📝 Test 2: SQL luôn lỗi → Bó tay sau 2 lần{C.RESET}")

    mock_db_fail = MockConnectorAlwaysFail()
    sc2 = SelfCorrection(connector=mock_db_fail)

    result2 = sc2.execute_with_retry(
        sql='SELECCT * FROM nowhere',
        schema='',
        max_retries=2,
    )

    if not result2["success"]:
        print(f"   {C.GREEN}✅ PASS — Đúng, bó tay sau {result2['retries']} lần!{C.RESET}")
        print(f"   {C.DIM}   Lỗi: {result2['error'][:80]}{C.RESET}")
        passed += 1
    else:
        print(f"   {C.RED}❌ FAIL — Lẽ ra phải thất bại!{C.RESET}")
        failed += 1

    # ── TEST 3: SQL đúng ngay lần 1 → Không cần retry ──
    print(f"\n{C.YELLOW}{'─'*60}{C.RESET}")
    print(f"{C.BOLD}📝 Test 3: SQL đúng ngay → 0 retry{C.RESET}")

    class MockConnectorOK:
        def execute(self, sql):
            return pd.DataFrame({"count": [42]})

    sc3 = SelfCorrection(connector=MockConnectorOK())
    result3 = sc3.execute_with_retry(
        sql='SELECT COUNT(*) FROM "Dim_Products"',
        max_retries=3,
    )

    if result3["success"] and result3["retries"] == 0:
        print(f"   {C.GREEN}✅ PASS — Thành công ngay lần 1, 0 retry!{C.RESET}")
        print(f"   {C.DIM}   Data: {result3['data'].to_dict()}{C.RESET}")
        passed += 1
    else:
        print(f"   {C.RED}❌ FAIL{C.RESET}")
        failed += 1

    # Tổng kết
    print(f"\n{C.CYAN}{'='*80}{C.RESET}")
    total = passed + failed
    print(f"{C.BOLD}📊 KẾT QUẢ: {C.GREEN}{passed}/{total} PASSED{C.RESET} | {C.RED}{failed}/{total} FAILED{C.RESET}")
    print(f"{C.CYAN}{'='*80}{C.RESET}\n")


if __name__ == "__main__":
    test_self_correction()
