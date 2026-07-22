from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class NLUResult(BaseModel):
    intent: str = Field(description="Mục đích của câu hỏi: AGGREGATION, RANKING, COMPARISON, FILTERING, TREND, DETAIL")
    is_relevant: bool = Field(default=True, description="Cờ chặn sớm: Câu hỏi có liên quan đến phân tích dữ liệu không?")
    is_safe: bool = Field(default=True, description="Cờ an toàn: Câu hỏi có vi phạm chính sách bảo mật, PII hay mục đích xấu (spam/hack) không?")
    rejection_reason: Optional[str] = Field(default=None, description="Lý do từ chối nếu is_relevant = false hoặc is_safe = false")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Các thực thể được nhắc đến (vd: thời gian, khu vực)")
    time_range: Optional[Dict[str, str]] = Field(default=None, description="Khoảng thời gian cần filter")
    suggested_chart: Optional[str] = Field(default=None, description="Loại biểu đồ user gợi ý")
    
class SQLResult(BaseModel):
    sql: str = Field(description="Câu lệnh SQL hoàn chỉnh đã pass validation")
    explanation: Optional[str] = Field(default=None, description="Lời giải thích logic của câu SQL")
    used_tables: List[str] = Field(default_factory=list, description="Danh sách các bảng đã dùng")
    is_valid: bool = Field(default=False)
    errors: List[str] = Field(default_factory=list)
    retry_count: int = Field(default=0)

class QueryResult(BaseModel):
    dataframe_json: Optional[str] = Field(default=None, description="Kết quả query dạng JSON orient='records'")
    columns: List[str] = Field(default_factory=list, description="Danh sách các cột")
    row_count: int = Field(default=0, description="Số lượng dòng trả về")
    execution_time_ms: float = Field(default=0.0, description="Thời gian chạy query")
    is_truncated: bool = Field(default=False, description="Cờ cảnh báo: True nếu dữ liệu bị ép LIMIT do quá lớn")
    is_cached: bool = Field(default=False, description="Cờ hiệu suất: True nếu kết quả được lấy từ bộ nhớ đệm Local Cache")
    error_message: Optional[str] = Field(default=None, description="Lỗi thực thi từ phía Database (Timeout, đứt mạng...) nếu có")

# check RLS
class UserContext(BaseModel):
    user_id: str
    username: str = Field(description="Tên hiển thị trên UI và dùng để ghi Log")
    role: str
    permissions: List[str] = Field(default_factory=list)
    allowed_schemas: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Các thuộc tính dùng cho RLS (Ví dụ: {'region': 'North', 'department': 'Sales'})")

class AnalysisResult(BaseModel):
    narrative: str = Field(description="Lời nhận xét phân tích số liệu (đã qua Template Injection)")
    chart_type: Optional[str] = Field(default=None, description="Loại biểu đồ: bar, line, pie, scatter...")
    chart_config_json: Optional[str] = Field(default=None, description="Cấu hình JSON của Plotly để vẽ biểu đồ")
    kpi_summary: Dict[str, Any] = Field(default_factory=dict, description="Các con số KPI nổi bật (vd: Tổng doanh thu = 10 tỷ)")
    warnings: List[str] = Field(default_factory=list, description="Cảnh báo mập mờ dữ liệu (Ví dụ: 'Dữ liệu tháng 5 bị thiếu 2 ngày cuối')")
    follow_up_questions: List[str] = Field(default_factory=list, description="Gợi ý 2-3 câu hỏi tiếp theo để User bấm vào (Tăng UX)")

class PipelineResponse(BaseModel):
    query_id: str = Field(description="ID duy nhất của câu hỏi")
    question: str = Field(description="Câu hỏi gốc của User")
    status: str = Field(default="success", description="Trạng thái cuối cùng: success, nlu_rejected, sql_error, db_error, system_error")
    error_message: Optional[str] = Field(default=None, description="Thông báo lỗi thân thiện hiển thị cho người dùng nếu status != success")
    nlu: NLUResult
    sql: SQLResult
    data: Optional[QueryResult] = None
    analysis: Optional[AnalysisResult] = None
    total_latency_ms: float = Field(description="Tổng thời gian xử lý toàn luồng")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Ghi nhận lượng Token đã dùng hoặc chi phí API LLM")