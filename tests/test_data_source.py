import pytest
from modules.data_source.sqlite_source import SQLiteConnector, create_sample_data
from modules.data_source.base import get_connector

@pytest.fixture
def connector():
    """Fixture tạo dữ liệu mẫu và trả về SQLiteConnector."""
    return create_sample_data()

def test_get_connector_factory():
    """Kiểm tra Factory function get_connector()."""
    conn = get_connector("sqlite")
    assert conn is not None
    assert conn.get_dialect() == "SQLite"

def test_get_foreign_keys(connector):
    """Kiểm tra hàm get_foreign_keys() quét đúng FK."""
    fks = connector.get_foreign_keys()
    assert isinstance(fks, list)
    assert len(fks) >= 2
    
    # Kiểm tra quan hệ Sales -> Customers
    sales_customer_fk = next((fk for fk in fks if fk["from_table"] == "Sales" and fk["to_table"] == "Customers"), None)
    assert sales_customer_fk is not None
    assert sales_customer_fk["from_column"] == "CustomerID"
    assert sales_customer_fk["to_column"] == "CustomerID"

    # Kiểm tra quan hệ Sales -> Products
    sales_product_fk = next((fk for fk in fks if fk["from_table"] == "Sales" and fk["to_table"] == "Products"), None)
    assert sales_product_fk is not None
    assert sales_product_fk["from_column"] == "ProductID"
    assert sales_product_fk["to_column"] == "ProductID"
    
    print(f"\n[+] Kết quả test_get_foreign_keys:")
    for fk in fks:
        print(f"    {fk['from_table']}.{fk['from_column']} ➔ {fk['to_table']}.{fk['to_column']}")

def test_get_sample_values(connector):
    """Kiểm tra hàm get_sample_values() lấy đúng giá trị mẫu."""
    regions = connector.get_sample_values("Customers", "Region")
    assert isinstance(regions, list)
    assert "Miền Bắc" in regions
    assert "Miền Nam" in regions
    assert len(regions) <= 50
    
    print(f"\n[+] Kết quả test_get_sample_values (Customers.Region):")
    print(f"    {regions}")

def test_get_schema(connector):
    """Kiểm tra đọc schema."""
    schema = connector.get_schema()
    assert len(schema) == 3
    table_names = [t["table_name"] for t in schema]
    assert "Customers" in table_names
    assert "Products" in table_names
    assert "Sales" in table_names
    
    print(f"\n[+] Kết quả test_get_schema:")
    print(f"    Đã đọc 3 bảng: {table_names}")