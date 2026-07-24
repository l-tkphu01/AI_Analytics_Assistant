import pytest
import sys
from dotenv import load_dotenv

# Đảm bảo load file .env từ thư mục gốc
load_dotenv()

from config.settings import settings
from modules.data_source.base import get_connector
from modules.schema.engine import SchemaEngine

def test_full_postgres_integration():
    """
    Test Integration: Cắm thẳng vào DB thật để xem Schema Engine 
    hoạt động trên 6 bảng Enterprise của PostgreSQL như thế nào.
    """
    # 1. Kiểm tra xem sếp đã đổi DATA_SOURCE thành postgresql chưa
    if settings.DATA_SOURCE != "postgresql":
        pytest.skip("Bỏ qua bài test vì .env chưa thiết lập DATA_SOURCE=postgresql")
        
    print("\n" + "="*70)
    print("🚀 BẮT ĐẦU CHẠY THỬ NGHIỆM TÍCH HỢP POSTGRESQL (ENTERPRISE SCHEMA)")
    print("="*70)
    
    # 2. Khởi tạo Connector và SchemaEngine
    try:
        connector = get_connector("postgresql")
        # Kiểm tra kết nối
        assert connector.test_connection() == True, "Không thể kết nối đến PostgreSQL! Sếp kiểm tra lại DATABASE_URL nhé."
        
        engine = SchemaEngine(connector)
        
        # 3. Kích hoạt toàn bộ Pipeline (Lấy Schema -> Cắt tỉa rác -> Lấy Mẫu -> Gom Quan hệ)
        final_prompt = engine.build_context()
        
        # 4. In ra kết quả tuyệt đẹp để sếp xem
        print("\n\n📊 KẾT QUẢ ĐẦU RA CỦA SCHEMA ENGINE (SẼ ĐƯỢC GỬI CHO AI):")
        print("-" * 70)
        print(final_prompt)
        print("-" * 70)
        
        # Kiểm tra nhanh một số đặc tính của Schema 6 bảng
        assert "Fact_Sales" in final_prompt
        assert "Dim_Customers" in final_prompt
        assert "QUAN HỆ CÁC BẢNG" in final_prompt
        assert "Fact_Sales.CustomerKey" in final_prompt
        
    except Exception as e:
        pytest.fail(f"Test thất bại do lỗi hệ thống: {e}")
