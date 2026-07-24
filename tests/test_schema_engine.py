import pytest
from modules.schema.engine import SchemaEngine

class MockConnector:
    """Mock Connector giả lập DB để test độc lập Schema Engine."""
    def get_schema(self):
        return [
            {
                "table_name": "Users",
                "columns": [
                    {"name": "UserID", "type": "INT"},
                    {"name": "Username", "type": "VARCHAR"},
                    {"name": "PasswordHash", "type": "VARCHAR"}, # Rác
                    {"name": "CreatedAt", "type": "TIMESTAMP"}   # Rác
                ]
            },
            {
                "table_name": "Orders",
                "columns": [
                    {"name": "OrderID", "type": "INT"},
                    {"name": "UserID", "type": "INT"},
                    {"name": "Status", "type": "VARCHAR"},
                    {"name": "UpdatedAt", "type": "TIMESTAMP"}   # Rác
                ]
            }
        ]
        
    def get_foreign_keys(self):
        return [
            {"from_table": "Orders", "from_column": "UserID", "to_table": "Users", "to_column": "UserID"}
        ]
        
    def get_sample_values(self, table, column, limit=50):
        if table == "Orders" and column == "Status":
            return ["Pending", "Completed", "Cancelled"]
        return []

@pytest.fixture
def engine():
    return SchemaEngine(MockConnector())

def test_prune_columns(engine):
    """Test RAG #1: Column Pruning"""
    raw_schema = engine.connector.get_schema()
    pruned = engine.prune_columns(raw_schema)
    
    # Bảng Users
    users_cols = [c["name"] for c in pruned[0]["columns"]]
    assert "UserID" in users_cols
    assert "Username" in users_cols
    assert "PasswordHash" not in users_cols # Bị loại bỏ
    assert "CreatedAt" not in users_cols    # Bị loại bỏ
    
    # Bảng Orders
    orders_cols = [c["name"] for c in pruned[1]["columns"]]
    assert "UpdatedAt" not in orders_cols   # Bị loại bỏ

def test_detect_relationships(engine):
    """Test Gộp 3 Lớp Auto-Detect (FK + Naming)"""
    rels = engine.detect_relationships()
    
    # DB_FK scan
    fk_rel = next((r for r in rels if r["source"] == "DB_FK"), None)
    assert fk_rel is not None
    assert fk_rel["from_table"] == "Orders"
    assert fk_rel["from_column"] == "UserID"
    
    # Naming Convention (Sẽ tự detect Users.UserID = Orders.UserID vì chứa chữ ID)
    # Tuy nhiên do tuple(sorted) đã khử trùng với DB_FK, nên rels có thể chỉ có 1
    assert len(rels) >= 1

def test_profile_columns(engine):
    """Test RAG #5: Data Profiling"""
    raw_schema = engine.connector.get_schema()
    profiled = engine.profile_columns(raw_schema)
    
    orders_table = profiled[1]
    status_col = next(c for c in orders_table["columns"] if c["name"] == "Status")
    
    assert "sample_values" in status_col
    assert status_col["sample_values"] == ["Pending", "Completed", "Cancelled"]

def test_format_schema_for_prompt(engine):
    context = engine.build_context()
    assert "CẤU TRÚC DATABASE" in context
    assert "QUAN HỆ CÁC BẢNG" in context
    assert "PasswordHash" not in context # Rác không xuất hiện trong prompt
    assert "Pending" in context # Mẫu Profiling xuất hiện trong prompt