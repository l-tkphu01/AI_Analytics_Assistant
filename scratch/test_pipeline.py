"""
TEST PIPELINE END-TO-END — Gõ câu hỏi trực tiếp trong Terminal
Chạy: python scratch/test_pipeline.py
"""
import os, sys, time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv()

if sys.stdout.encoding.lower() != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

# === Bảng màu ===
class C:
    CYAN = '\033[96m'; GREEN = '\033[92m'; YELLOW = '\033[93m'
    RED = '\033[91m'; MAGENTA = '\033[95m'; BOLD = '\033[1m'
    RESET = '\033[0m'; DIM = '\033[2m'

# === Khởi tạo tất cả module 1 lần ===
print(f"\n{C.CYAN}{C.BOLD}{'='*70}{C.RESET}")
print(f"{C.CYAN}{C.BOLD}  🚀 AI ANALYTICS ASSISTANT — TEST PIPELINE END-TO-END{C.RESET}")
print(f"{C.CYAN}{C.BOLD}{'='*70}{C.RESET}\n")

print(f"{C.DIM}⏳ Đang khởi tạo các module...{C.RESET}")

from modules.security.guardrails import validate_question_safety
from modules.security.rls import generate_rls_prompt
from modules.security.auth import mock_login
from modules.nlu.engine import NLUEngine
from modules.schema.indexer import SchemaIndexer
from modules.sql.generator import SQLGenerator
from modules.sql.validator import SQLValidator
from modules.sql.self_correction import SelfCorrection
from modules.data_source.postgresql import PostgreSQLConnector
from core.models import UserContext
from core.llm_providers import LLMProvider

# Kết nối DB
db = PostgreSQLConnector()
db.connect()

# Khởi tạo module
nlu = NLUEngine()
indexer = SchemaIndexer(connector=db)
gen = SQLGenerator()
val = SQLValidator()
sc = SelfCorrection(connector=db)

# Index schema vào ChromaDB (chỉ lần đầu, lần sau dùng cache)
print(f"{C.DIM}⏳ Đang index schema vào ChromaDB...{C.RESET}")
indexer.index_schema()

# Mock user (admin = full quyền)
from modules.security.auth import verify_token
token = mock_login("admin")
user = verify_token(token)

chat_history = []

print(f"{C.GREEN}✅ Tất cả module đã sẵn sàng!{C.RESET}")
print(f"{C.DIM}   User: {user.username} ({user.role}){C.RESET}")
print(f"{C.YELLOW}   Gõ 'quit' để thoát | 'user:nam' để đổi user{C.RESET}\n")

while True:
    question = input(f"{C.BOLD}🤵 Sếp hỏi: {C.RESET}").strip()
    if not question:
        continue
    if question.lower() == 'quit':
        print(f"\n{C.CYAN}👋 Bye bye sếp!{C.RESET}\n")
        break
    if question.lower().startswith('user:'):
        new_user = question.split(':')[1].strip()
        token = mock_login(new_user)
        user = verify_token(token)
        chat_history = []
        print(f"{C.GREEN}✅ Đã đổi user → {user.username} ({user.role}){C.RESET}\n")
        continue

    start = time.time()

    # ── BƯỚC 1: GUARDRAILS ──
    print(f"\n{C.DIM}[1/7] Guardrails...{C.RESET}", end=" ")
    is_safe, guard_msg = validate_question_safety(question)
    if not is_safe:
        print(f"{C.RED}❌ CHẶN: {guard_msg}{C.RESET}\n")
        continue
    print(f"{C.GREEN}✅{C.RESET}")

    # ── BƯỚC 2: REWRITING ──
    print(f"{C.DIM}[2/7] Query Expansion...{C.RESET}", end=" ")
    expanded = nlu.rewrite_question(question, chat_history=chat_history)
    primary = expanded[0] if expanded else question
    print(f"{C.GREEN}✅ {len(expanded)} biến thể{C.RESET}")
    for i, q in enumerate(expanded, 1):
        print(f"   {C.DIM}V{i}: {q}{C.RESET}")

    # ── BƯỚC 3: VECTOR SEARCH ──
    print(f"{C.DIM}[3/7] Vector Search...{C.RESET}", end=" ")
    schema_text = ""
    for q in expanded:
        try:
            r = indexer.get_relevant_schema_for_prompt(q)
            if len(r) > len(schema_text):
                schema_text = r
        except: pass
    print(f"{C.GREEN}✅ {len(schema_text)} chars schema{C.RESET}")

    # ── BƯỚC 4: NLU ──
    print(f"{C.DIM}[4/7] NLU Intent...{C.RESET}", end=" ")
    cols = indexer._cached_profiled_schema if indexer._cached_profiled_schema else None
    nlu_result = nlu.analyze_intent(primary, schema_columns=cols)
    intent = nlu_result.get('intent')
    print(f"{C.GREEN}✅ Intent={intent}{C.RESET}")

    if intent == 'GENERAL':
        print(f"\n{C.MAGENTA}{'─'*70}{C.RESET}")
        print(f"{C.BOLD}🤖 AI:{C.RESET} Xin chào! Tôi là trợ lý phân tích dữ liệu. Hãy hỏi tôi về doanh thu, khách hàng, hoặc sản phẩm nhé!")
        print(f"{C.MAGENTA}{'─'*70}{C.RESET}\n")
        continue
    
    if intent == 'METADATA':
        print(f"\n{C.DIM}[5/7] Trả lời Metadata...{C.RESET}", end=" ")
        llm = LLMProvider.get_sql_llm()
        prompt = f"Dựa vào thông tin schema sau đây, hãy trả lời câu hỏi của người dùng ngắn gọn, dễ hiểu bằng tiếng Việt.\n\nSchema:\n{schema_text}\n\nCâu hỏi: {question}"
        ans = llm.invoke(prompt).content.strip()
        print(f"{C.GREEN}✅{C.RESET}")
        print(f"\n{C.MAGENTA}{'─'*70}{C.RESET}")
        print(f"{C.BOLD}🤖 AI (Giải thích dữ liệu):{C.RESET}\n{ans}")
        print(f"{C.MAGENTA}{'─'*70}{C.RESET}\n")
        continue

    # ── BƯỚC 5: SQL GENERATOR ──
    print(f"{C.DIM}[5/7] SQL Generator...{C.RESET}", end=" ")
    rls_prompt = generate_rls_prompt(user)
    gen_result = gen.generate_sql(primary, schema_text, rls_prompt, nlu_result)
    if not gen_result["success"]:
        print(f"{C.RED}❌ {gen_result['error']}{C.RESET}\n")
        continue
    print(f"{C.GREEN}✅{C.RESET}")

    # ── BƯỚC 6: SQL VALIDATOR ──
    print(f"{C.DIM}[6/7] SQL Validator...{C.RESET}", end=" ")
    val_result = val.validate(gen_result["sql"], user=user)
    if not val_result["valid"]:
        print(f"{C.RED}❌ {val_result['error']}{C.RESET}\n")
        continue
    print(f"{C.GREEN}✅{C.RESET}")

    # ── BƯỚC 7: EXECUTE + SELF-CORRECTION ──
    print(f"{C.DIM}[7/7] Execute SQL...{C.RESET}", end=" ")
    exec_result = sc.execute_with_retry(val_result["sql"], schema_text, max_retries=3)
    elapsed = int((time.time() - start) * 1000)

    if not exec_result["success"]:
        print(f"{C.RED}❌ {exec_result['error']}{C.RESET}\n")
        continue
    print(f"{C.GREEN}✅ {exec_result['retries']} retries{C.RESET}")

    # ── KẾT QUẢ ──
    df = exec_result["data"]
    
    # === THÊM CLS MASKING VÀO REPL ===
    from modules.security.cls import CLSManager
    cls_manager = CLSManager()
    df = cls_manager.apply_masking(df, user)
    # =================================
    
    print(f"\n{C.MAGENTA}{'─'*70}{C.RESET}")
    print(f"{C.BOLD}📊 SQL:{C.RESET}")
    print(f"   {C.CYAN}{exec_result['sql_final']}{C.RESET}")
    print(f"\n{C.BOLD}📋 KẾT QUẢ ({len(df)} dòng, {elapsed}ms):{C.RESET}")
    if len(df) > 0:
        print(df.to_string(index=False))
    else:
        print(f"   {C.YELLOW}(Không có dữ liệu){C.RESET}")
    print(f"{C.MAGENTA}{'─'*70}{C.RESET}\n")

    # Lưu lịch sử
    chat_history.append({"role": "user", "content": question})
    chat_history.append({"role": "assistant", "content": f"Kết quả: {primary}"})
    if len(chat_history) > 6:
        chat_history = chat_history[-6:]
