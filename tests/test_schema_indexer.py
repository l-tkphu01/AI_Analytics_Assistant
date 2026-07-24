"""
Test Tích Hợp: Schema Indexer + ChromaDB + PostgreSQL
Kiểm tra toàn bộ Pipeline Bước 2: Index → Search → Rerank
[BẢN MÀU SẮC ĐẸP MẮT]: Trả lại giao diện màu sắc, Emojis, siêu rõ ràng như sếp yêu cầu!
"""
import pytest
import sys
from dotenv import load_dotenv
load_dotenv()

# Bắt buộc ép stdout dùng UTF-8 để in được Tiếng Việt có dấu và Emoji trên Windows Terminal
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config.settings import settings
from modules.data_source.base import get_connector
from modules.schema.indexer import SchemaIndexer

# ==========================================
# BẢNG MÀU TÙY CHỈNH CHO TERMINAL
# ==========================================
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

def print_section(title):
    print(f"\n{C.CYAN}{C.BOLD}{'=' * 80}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}🚀 {title.upper()}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'=' * 80}{C.RESET}")

def print_search_results(question, results):
    print(f"\n{C.YELLOW}{C.BOLD}💬 CÂU HỎI:{C.RESET} {C.BOLD}\"{question}\"{C.RESET}")
    if not results:
        print(f"    {C.RED}❌ Không tìm thấy bảng nào liên quan.{C.RESET}")
        return
        
    print(f"    {C.MAGENTA}🎯 TÌM THẤY {len(results)} BẢNG LIÊN QUAN NHẤT:{C.RESET}")
    for i, r in enumerate(results, 1):
        # Format cột thành chuỗi dễ đọc, có chèn thêm [FK -> ...] nếu có
        cols = []
        for c in r["matched_columns"][:3]:
            col_str = f"{C.GREEN}{c['column']}{C.RESET} ({C.YELLOW}{c['score']:.2f}{C.RESET})"
            if "metadata" in c and c["metadata"] and c["metadata"].get("is_foreign_key"):
                col_str += f" {C.MAGENTA}[FK ➔ {c['metadata']['fk_references']}]{C.RESET}"
            cols.append(col_str)
            
        cols_str = ", ".join(cols)
        if len(r["matched_columns"]) > 3:
            cols_str += f", và {len(r['matched_columns']) - 3} cột khác..."
            
        print(f"        {C.BOLD}{i}. 🏷️ {C.BLUE}{r['table_name']:<15}{C.RESET} | Điểm: {C.GREEN}{C.BOLD}{r['score']:.4f}{C.RESET} | Khớp: {cols_str}")

def test_schema_indexer_full_pipeline():
    """
    Test toàn bộ Pipeline Bước 2 với hiển thị siêu đẹp (Màu sắc + Emoji).
    """
    if settings.DATA_SOURCE != "postgresql":
        pytest.skip("Bỏ qua vì chưa thiết lập DATA_SOURCE=postgresql")
    
    connector = get_connector("postgresql")
    assert connector.test_connection(), "Không kết nối được PostgreSQL!"
    
    indexer = SchemaIndexer(connector)
    
    print_section("BƯỚC 1: KHỞI TẠO & NHÚNG (EMBEDDING) SCHEMA VÀO CHROMADB")
    num_indexed = indexer.index_schema()
    print(f"\n{C.GREEN}{C.BOLD}✅ Đã nhúng thành công {num_indexed} cột vào Vector Database (ChromaDB)!{C.RESET}\n")
    assert num_indexed > 0, "Không có cột nào được index!"
    
    print_section("BƯỚC 2: TÌM KIẾM NGỮ NGHĨA (SEMANTIC SEARCH) & RERANK")
    
    # Test case 1
    q1 = "Tổng doanh thu bán hàng theo từng quý"
    results1 = indexer.search_relevant_tables(q1)
    print_search_results(q1, results1)
    
    # Test case 2
    q2 = "Sản phẩm thương hiệu Apple bán chạy nhất"
    results2 = indexer.search_relevant_tables(q2)
    print_search_results(q2, results2)
    
    # Test case 3
    q3 = "Kiểm tra hàng tồn kho sắp hết"
    results3 = indexer.search_relevant_tables(q3)
    print_search_results(q3, results3)
    
    print_section("BƯỚC 3: KIỂM TRA ĐẦU RA CHO PROMPT (SCHEMA ĐÃ LỌC)")
    test_question = "Doanh thu thương hiệu Apple tại Miền Bắc"
    filtered_prompt = indexer.get_relevant_schema_for_prompt(test_question)
    
    lines = filtered_prompt.split('\n')
    tables_in_prompt = [line.replace('### Bảng `', '').replace('`', '') for line in lines if line.startswith('### Bảng ')]
    
    print(f"\n{C.YELLOW}{C.BOLD}💬 CÂU HỎI TEST:{C.RESET} {C.BOLD}\"{test_question}\"{C.RESET}")
    print(f"\n{C.GREEN}✅ Thay vì nạp toàn bộ 6 bảng, hệ thống thông minh chỉ chọn ra {C.BOLD}{len(tables_in_prompt)} bảng{C.RESET}{C.GREEN} liên quan nhất để đưa cho AI:{C.RESET}")
    for t in tables_in_prompt:
        print(f"     {C.CYAN}👉 {t}{C.RESET}")
        
    assert len(tables_in_prompt) > 0, "Phải chọn ra ít nhất 1 bảng"
    assert "Fact_Sales" in tables_in_prompt or "Dim_Products" in tables_in_prompt, "Nên tìm thấy bảng Sales hoặc Products"
    assert "QUAN HỆ CÁC BẢNG (JOIN PATHS):" in filtered_prompt, "Prompt phải chứa thông tin quan hệ (JOIN)"
    
    print(f"\n{C.GREEN}{C.BOLD}🎉 TẤT CẢ BÀI TEST ĐÃ PASSED! ĐẦU RA SẠCH SẼ, SẴN SÀNG CHO AI LÀM VIỆC.{C.RESET}\n")
