"""
AI ANALYTICS ASSISTANT — PIPELINE HOÀN CHỈNH 🚀
Nối tất cả module thành 1 luồng xử lý End-to-End:

Câu hỏi User
  → [1. Guardrails]     Kiểm tra an toàn
  → [2. Rewriting]      Viết lại 3 câu (Query Expansion)
  → [3. Vector Search]  Tìm bảng/cột liên quan  ┐
  → [4. NLU Engine]     Bóc intent + entities     ┘ Chạy song song
  → [5. SQL Generator]  Viết SQL
  → [6. SQL Validator]  Kiểm tra cú pháp + bảo mật + LIMIT
  → [7. Self-Correction] Chạy DB + tự sửa nếu lỗi
  → Trả kết quả cho User
"""
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
import uvicorn
import time
from concurrent.futures import ThreadPoolExecutor
from core.logger import get_logger
from config.settings import settings
from config.database import init_databases

# === SECURITY ===
from core.models import UserContext
from modules.security.auth import mock_login, get_current_user
from modules.security.rbac import validate_table_access
from modules.security.rls import generate_rls_prompt, validate_rls_sql
from modules.security.guardrails import validate_question_safety

# === NLU + SCHEMA + SQL ===
from modules.nlu.engine import NLUEngine
from modules.schema.indexer import SchemaIndexer
from modules.sql.generator import SQLGenerator
from modules.sql.validator import SQLValidator
from modules.sql.self_correction import SelfCorrection
from modules.conversation.manager import ConversationManager
from modules.security.cls import CLSManager
from modules.visualization.recommender import VizRecommender
from modules.analysis.narrative import NarrativeGenerator
from modules.analysis.statistical import StatisticalAnalyzer

logger = get_logger(__name__)

# === GLOBAL INSTANCES (Khởi tạo 1 lần, dùng lại mọi request) ===
nlu_engine = None
schema_indexer = None
sql_generator = None
sql_validator = None
self_correction = None
conv_manager = None
cls_manager = None  # [Singleton] Column-Level Security
viz_recommender = None  # [Singleton] AI Visualization Recommender
narrative_gen = None  # [Singleton] AI Narrative Generator
stat_analyzer = None  # [Singleton] Statistical Analyzer (thuần toán học)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global nlu_engine, schema_indexer, sql_generator, sql_validator, self_correction, conv_manager, cls_manager, viz_recommender, narrative_gen, stat_analyzer

    logger.info("=" * 60)
    logger.info(f"🚀 KHỞI ĐỘNG AI ANALYTICS ASSISTANT (Môi trường: {settings.ENVIRONMENT})")
    logger.info("=" * 60)

    # 1. Khởi tạo Database connections
    init_databases()

    # 2. Khởi tạo DB Connector
    from modules.data_source.postgresql import PostgreSQLConnector
    db_connector = PostgreSQLConnector()
    db_connector.connect()

    # 3. Khởi tạo các module (truyền connector cho module cần DB)
    nlu_engine = NLUEngine()
    schema_indexer = SchemaIndexer(connector=db_connector)
    sql_generator = SQLGenerator()
    sql_validator = SQLValidator(connector=db_connector)
    self_correction = SelfCorrection(connector=db_connector)
    conv_manager = ConversationManager()
    cls_manager = CLSManager()  # [Singleton] Đọc file sensitive_columns.json 1 lần duy nhất
    viz_recommender = VizRecommender()  # [Singleton] AI chọn biểu đồ
    narrative_gen = NarrativeGenerator()  # [Singleton] AI viết nhận xét
    stat_analyzer = StatisticalAnalyzer()  # [Singleton] Phân tích thống kê (thuần toán)

    # 4. Warm-up Schema Cache & Vector DB trong background (tránh block startup)
    import threading
    def warmup_schema():
        try:
            logger.info("Đang khởi tạo Schema Index trong background...")
            schema_indexer.index_schema()
            logger.info("Hoàn tất khởi tạo Schema Index.")
        except Exception as e:
            logger.error(f"Lỗi khởi tạo Schema Index: {e}")
            
    threading.Thread(target=warmup_schema, daemon=True).start()

    logger.info("✅ Tất cả module đã sẵn sàng!")
    yield
    logger.info("🛑 Đã tắt máy chủ AI Analytics.")


app = FastAPI(
    title="AI Analytics Assistant API",
    description="Hệ thống trợ lý phân tích dữ liệu AI — Pipeline End-to-End 🚀",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/")
def health_check():
    return {"status": "success", "message": "AI Analytics Assistant đang chạy! 🚀"}


# =======================================================================
# 🎫 1. API ĐĂNG NHẬP (Lấy Token)
# =======================================================================
@app.get("/api/auth/login")
def login(username: str):
    """
    Đăng nhập để lấy Token.
    Thử: 'admin' (full quyền) hoặc 'nam' (chỉ xem Miền Nam).
    """
    token = mock_login(username)
    return {"access_token": token, "token_type": "bearer"}


# =======================================================================
# 🕒 2. API LẤY LỊCH SỬ CHAT (History)
# =======================================================================
@app.get("/api/v1/history")
def get_chat_history(current_user: UserContext = Depends(get_current_user)):
    """Trả về toàn bộ lịch sử chat của user từ SQLite (Bao gồm cả chart_json)"""
    history = conv_manager.get_full_session(current_user.user_id)
    return {"status": "success", "data": history}


# =======================================================================
# 🗑️ 2b. API XÓA LỊCH SỬ CHAT
# =======================================================================
@app.delete("/api/v1/history")
def clear_chat_history(current_user: UserContext = Depends(get_current_user)):
    """Xóa toàn bộ lịch sử chat của user khỏi Database."""
    conv_manager.clear_session(current_user.user_id)
    return {"status": "success", "message": "Đã xóa lịch sử chat."}


# =======================================================================
# 🔒 3. API TRUY VẤN — PIPELINE HOÀN CHỈNH
# =======================================================================
@app.post("/api/v1/query")
def process_query(question: str, current_user: UserContext = Depends(get_current_user)):
    """
    API chính: Nhận câu hỏi tiếng Việt → Trả kết quả từ Database.
    Pipeline: Guardrails → Rewriting → Vector Search + NLU → SQL → Validate → Execute
    """
    start_time = time.time()
    user_id = current_user.user_id  # [FIX Bug 1] Dùng user_id ổn định thay vì username (tên hiển thị)
    final_response = None

    try:
        # Lấy lịch sử chat của user
        user_history = conv_manager.get_memory(user_id, limit=3)

        # ──────────────────────────────────────────────────────
        # BƯỚC 1: GUARDRAILS — Kiểm tra an toàn
        # ──────────────────────────────────────────────────────
        is_safe, guard_msg = validate_question_safety(question, chat_history=user_history)
        if not is_safe:
            return {
                "status": "blocked",
                "error": guard_msg,
                "pipeline_step": "1_guardrails"
            }

        # ──────────────────────────────────────────────────────
        # BƯỚC 2: REWRITING + QUERY EXPANSION (1 → 3 câu)
        # ──────────────────────────────────────────────────────
        # Lấy lại context từ lịch sử chat trước khi đoán ý định
        expanded_queries = nlu_engine.rewrite_question(question, chat_history=user_history)
        primary_query = expanded_queries[0] if expanded_queries else question
        logger.info(f"Pipeline Bước 2: Query Expansion → {len(expanded_queries)} biến thể. Primary: '{primary_query}'")

        # ──────────────────────────────────────────────────────
        # BƯỚC 3: PHÂN LOẠI Ý ĐỊNH (Dùng câu đã có Context)
        # ──────────────────────────────────────────────────────
        # Lấy schema cache để gợi ý cho NLU (nếu có)
        cols = schema_indexer._cached_profiled_schema if schema_indexer._cached_profiled_schema else None
        
        try:
            # Phân loại dựa trên câu đã được làm rõ ngữ cảnh (primary_query) thay vì câu gốc ngầm ý
            nlu_result = nlu_engine.analyze_intent(primary_query, schema_columns=cols)
        except Exception as e:
            logger.warning(f"NLU lỗi: {e}")
            nlu_result = {"intent": "GENERAL", "original_question": primary_query}
            
        intent = nlu_result.get("intent", "")
        logger.info(f"Pipeline Bước 3: NLU Intent phát hiện: {intent}")

        # XỬ LÝ NHANH CÁC INTENT GIAO TIẾP (Không cần chạy DB)
        if intent == "GENERAL":
            elapsed_ms = int((time.time() - start_time) * 1000)
            final_response = {
                "status": "success",
                "data": [{"Message": "Xin chào! Tôi là trợ lý phân tích dữ liệu AI. Hãy hỏi tôi về doanh thu, khách hàng, hoặc sản phẩm nhé!"}],
                "metadata": {
                    "user": f"{current_user.username}",
                    "question_original": question,
                    "question_rewritten": primary_query,
                    "query_expansion": expanded_queries,
                    "nlu_intent": "GENERAL",
                    "sql_final": "-- Xin chào (GENERAL intent)",
                    "retries": 0,
                    "rows_returned": 1,
                    "elapsed_ms": elapsed_ms
                }
            }
            return final_response

        # ──────────────────────────────────────────────────────
        # BƯỚC 4: VECTOR SEARCH (Tìm bảng liên quan)
        # ──────────────────────────────────────────────────────
        schema_text = ""
        try:
            results = []
            for q in expanded_queries:
                try:
                    result = schema_indexer.get_relevant_schema_for_prompt(q)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"Vector Search lỗi cho '{q[:30]}': {e}")
            
            # Gộp kết quả: Lấy text dài nhất (chứa nhiều bảng nhất)
            schema_text = max(results, key=len) if results else ""
        except Exception as e:
            logger.warning(f"Lỗi khối Vector Search: {e}")
            schema_text = "Không có thông tin schema."
            
        logger.info(f"Pipeline Bước 4: Schema Context size = {len(schema_text)} chars")
        
        if intent == "GENERAL":
            elapsed_ms = int((time.time() - start_time) * 1000)
            final_response = {
                "status": "success",
                "data": [{"Message": "Xin chào! Tôi là trợ lý phân tích dữ liệu AI. Hãy hỏi tôi về doanh thu, khách hàng, hoặc sản phẩm nhé!"}],
                "metadata": {
                    "user": f"{current_user.username} ({current_user.role})",
                    "question_original": question,
                    "nlu_intent": "GENERAL",
                    "sql_final": "-- Xin chào (GENERAL intent)",
                    "elapsed_ms": elapsed_ms
                }
            }
            return final_response
            
        if intent == "METADATA":
            from core.llm_providers import LLMProvider
            llm = LLMProvider.get_sql_llm()
            prompt = f"Dựa vào thông tin schema sau đây, hãy trả lời câu hỏi của người dùng ngắn gọn, dễ hiểu bằng tiếng Việt.\n\nSchema:\n{schema_text}\n\nCâu hỏi: {question}"
            ans = llm.invoke(prompt).content.strip()
            elapsed_ms = int((time.time() - start_time) * 1000)
            final_response = {
                "status": "success",
                "data": [{"Message": ans}],
                "metadata": {
                    "user": f"{current_user.username} ({current_user.role})",
                    "question_original": question,
                    "nlu_intent": "METADATA",
                    "sql_final": "-- Trả lời về cấu trúc DB (METADATA intent)",
                    "elapsed_ms": elapsed_ms
                }
            }
            return final_response

        # ──────────────────────────────────────────────────────
        # BƯỚC 5: SQL GENERATOR — Viết SQL
        # ──────────────────────────────────────────────────────
        rls_prompt = generate_rls_prompt(current_user)

        gen_result = sql_generator.generate_sql(
            question=primary_query,
            schema=schema_text,
            rls_prompt=rls_prompt,
            nlu_result=nlu_result
        )

        if not gen_result["success"]:
            final_response = {
                "status": "error",
                "error": f"SQL Generator thất bại: {gen_result['error']}",
                "pipeline_step": "5_sql_generator"
            }
            return final_response

        raw_sql = gen_result["sql"]
        
        # Xử lý trường hợp CHỐNG CHÉM GIÓ: Khi người dùng hỏi thông tin không có trong DB
        if raw_sql.strip() == "NO_DATA":
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "success",  # Vẫn coi là success để hiển thị text bình thường trên UI
                "data": [{"Message": "Dữ liệu bạn yêu cầu hiện không có trong hệ thống cơ sở dữ liệu của công ty. Tôi chỉ có thể phân tích các thông tin liên quan đến Doanh thu, Khách hàng, Sản phẩm và Tồn kho."}],
                "metadata": {
                    "user": f"{current_user.username} ({current_user.role})",
                    "question_original": question,
                    "nlu_intent": "GENERAL", # Ép kiểu GENERAL để UI không hiển thị dạng bảng
                    "sql_final": "-- NO DATA FOUND",
                    "elapsed_ms": elapsed_ms
                }
            }

        # ──────────────────────────────────────────────────────
        # BƯỚC 6: SQL VALIDATOR — Kiểm tra + Bảo mật + LIMIT
        # ──────────────────────────────────────────────────────
        val_result = sql_validator.validate(raw_sql, user=current_user)

        if not val_result["valid"]:
            final_response = {
                "status": "error",
                "error": f"SQL Validator từ chối: {val_result['error']}",
                "pipeline_step": "6_sql_validator",
                "sql_rejected": raw_sql
            }
            return final_response

        safe_sql = val_result["sql"]

        # ──────────────────────────────────────────────────────
        # BƯỚC 7: SELF-CORRECTION — Chạy DB + Tự sửa nếu lỗi
        # ──────────────────────────────────────────────────────
        exec_result = self_correction.execute_with_retry(
            sql=safe_sql,
            schema=schema_text,
            max_retries=3
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        if not exec_result["success"]:
            final_response = {
                "status": "error",
                "error": f"SQL thất bại sau {exec_result['retries']} lần retry: {exec_result['error']}",
                "pipeline_step": "7_self_correction",
                "sql_final": exec_result["sql_final"],
                "elapsed_ms": elapsed_ms
            }
            return final_response

        # ──────────────────────────────────────────────────────
        # THÀNH CÔNG! Lưu lịch sử chat + Trả kết quả
        # ──────────────────────────────────────────────────────
        # Convert DataFrame → JSON
        df = exec_result["data"]
        
        # --- ÁP DỤNG COLUMN-LEVEL SECURITY (CLS) ---
        df = cls_manager.apply_masking(df, current_user)
        # -------------------------------------------
        
        data_records = df.to_dict(orient="records")

        # ──────────────────────────────────────────────────────
        # BƯỚC 8+9: AI VISUALIZATION + NARRATIVE — Chạy SONG SONG
        # Cả hai chỉ cần: df + question + intent → Không phụ thuộc nhau
        # ──────────────────────────────────────────────────────
        from concurrent.futures import ThreadPoolExecutor

        chart_config = None
        narrative = None
        nlu_intent = nlu_result.get("intent", "GENERAL")
        should_run_ai = nlu_intent not in ("GENERAL", "METADATA")

        if should_run_ai:
            # Chuẩn bị DataFrame sạch cho Narrative (lọc cột bị CLS che "***")
            df_clean = df.copy()
            for col in df_clean.columns:
                if df_clean[col].dtype == object:
                    mask_count = (df_clean[col] == "***").sum()
                    if mask_count > 0:
                        df_clean = df_clean.drop(columns=[col])
                        logger.info(f"Narrative: Đã loại cột '{col}' (bị CLS che {mask_count} dòng).")

            def _run_viz():
                try:
                    cfg = viz_recommender.suggest(df, question, nlu_intent)
                    logger.info(f"Viz AI: Chọn biểu đồ '{cfg.get('chart_type')}' — {cfg.get('reason', '')}")
                    return cfg
                except Exception as e:
                    logger.warning(f"Viz AI: Lỗi chọn biểu đồ: {e}. Bỏ qua.")
                    return None

            def _run_narrative():
                try:
                    # Chạy Statistical Analysis TRƯỚC (thuần toán, cực nhanh ~5ms)
                    stat_result = stat_analyzer.analyze(df_clean, nlu_intent)
                    return narrative_gen.generate(df_clean, question, nlu_intent, stat_insights=stat_result)
                except Exception as e:
                    logger.warning(f"Narrative AI: Lỗi sinh nhận xét: {e}. Bỏ qua.")
                    return None

            # 🚀 Chạy song song — Tiết kiệm ~1 giây
            with ThreadPoolExecutor(max_workers=2) as executor:
                viz_future = executor.submit(_run_viz)
                nar_future = executor.submit(_run_narrative)
                chart_config = viz_future.result()
                narrative = nar_future.result()

        # ⏱️ Tính thời gian SAU KHI cả Viz + Narrative đều xong (chính xác!)
        elapsed_ms = round((time.time() - start_time) * 1000)


        final_response = {
            "status": "success",
            "data": data_records,
            "chart_config": chart_config,
            "narrative": narrative,
            "metadata": {
                "user": f"{current_user.username} ({current_user.role})",
                "question_original": question,
                "question_rewritten": primary_query,
                "query_expansion": expanded_queries,
                "nlu_intent": nlu_result.get("intent"),
                "sql_final": exec_result["sql_final"],
                "retries": exec_result["retries"],
                "rows_returned": len(data_records),
                "elapsed_ms": elapsed_ms
            }
        }
        return final_response

    except Exception as e:
        logger.error(f"Pipeline Failed: {e}")
        final_response = {"status": "error", "error": "Hệ thống gặp lỗi nội bộ. Vui lòng thử lại sau.", "pipeline_step": "system_error"}
        return final_response
    
    finally:
        # ──────────────────────────────────────────────────────
        # LƯU LỊCH SỬ CHAT VÀO SQLITE
        # ──────────────────────────────────────────────────────
        if final_response:
            # [FIX Bug 4] Không lưu tin nhắn bị Guardrails chặn (tránh ô nhiễm lịch sử)
            if final_response.get("status") == "blocked":
                pass  # Bỏ qua, không ghi vào DB
            else:
                ai_msg = "Không tìm thấy dữ liệu"
                chart_json_str = None
                save_data = None
                save_sql = None
                
                if final_response.get("status") == "success" and final_response.get("data"):
                    # Tạo bản xem trước kết quả
                    ai_msg = f"Đã trả về {len(final_response['data'])} dòng dữ liệu."
                    if len(final_response['data']) == 1 and "Message" in final_response['data'][0]:
                        ai_msg = final_response['data'][0]["Message"]
                    
                    # [FIX Bug 3] Giới hạn data lưu vào session (tối đa 50 dòng)
                    raw_data = final_response.get("data")
                    if raw_data and len(raw_data) > 50:
                        save_data = raw_data[:50]  # Chỉ lưu 50 dòng đầu
                        logger.info(f"Session: Cắt data từ {len(raw_data)} → 50 dòng để tiết kiệm dung lượng.")
                    else:
                        save_data = raw_data
                    
                    save_sql = final_response.get("metadata", {}).get("sql_final") if final_response.get("metadata") else None
                    chart_json_str = final_response.get("chart_json")
                    
                elif final_response.get("error"):
                    ai_msg = final_response["error"]
                    
                conv_manager.add_turn(
                    session_id=user_id,   # [FIX Bug 1] Dùng user_id ổn định
                    user_id=user_id,
                    user_msg=question,
                    ai_msg=ai_msg,
                    chart_json=chart_json_str,
                    data=save_data,
                    sql=save_sql,
                    chart_config=final_response.get("chart_config"),  # Lưu cấu hình biểu đồ AI chọn
                    narrative=final_response.get("narrative")  # Lưu nhận xét AI
                )


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8000, reload=settings.DEBUG)