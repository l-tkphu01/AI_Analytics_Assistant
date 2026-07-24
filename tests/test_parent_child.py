import os
import json
import sys
import chromadb

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

# Bắt buộc ép stdout dùng UTF-8 để in được Tiếng Việt có dấu và Emoji trên Windows Terminal
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def print_parent_child_demo():
    print(f"\n{C.CYAN}{C.BOLD}{'=' * 80}{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}🧠 MINH HỌA PHƯƠNG PHÁP PARENT-CHILD TRONG VECTOR DATABASE{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}{'=' * 80}{C.RESET}\n")
    
    # 1. Kết nối vào ChromaDB đã lưu trong Project thật
    db_path = r"D:\Đại học\DATA_ENGINEERING\AI_Analytics_Assistant\data\chroma_db"
    
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection(name="schema_columns")
    
    # 2. Lấy 46 Vector ra xem
    results = collection.get(limit=46, include=["documents", "metadatas"])
    
    docs = results["documents"]
    metas = results["metadatas"]
    
    for i in range(len(docs)):
        print(f"{C.BLUE}🔹 DOCUMENT #{i+1}:{C.RESET}")
        print(f"   {C.YELLOW}[CHILD - Nội dung được Embed thành Vector]:{C.RESET}")
        print(f"   {C.GREEN}👉 \"{docs[i]}\"{C.RESET}\n")
        
        print(f"   {C.MAGENTA}[PARENT - Thông tin truy xuất ngược (RAW JSON)]:{C.RESET}")
        # In ra dạng JSON format đẹp mắt
        formatted_json = json.dumps(metas[i], indent=4, ensure_ascii=False)
        for line in formatted_json.split("\n"):
            print(f"   {C.CYAN}{line}{C.RESET}")
            
        print(f"{C.BOLD}{'-' * 80}{C.RESET}\n")
        
    print(f"{C.YELLOW}💡 GIẢI THÍCH:{C.RESET}")
    print(f"{C.RESET}- Khi sếp hỏi, AI sẽ so sánh câu hỏi với phần {C.YELLOW}[CHILD]{C.RESET}.")
    print(f"{C.RESET}- Nếu {C.YELLOW}[CHILD]{C.RESET} khớp, hệ thống sẽ dùng thẻ {C.MAGENTA}[PARENT] (Table){C.RESET} để lấy CẢ BẢNG đó đưa cho Llama 3 sinh SQL.")
    print(f"{C.CYAN}{C.BOLD}{'=' * 80}{C.RESET}\n")

if __name__ == "__main__":
    print_parent_child_demo()
