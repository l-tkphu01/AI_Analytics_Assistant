import os
import sys

# Thêm root_dir vào sys.path để import được modules
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from dotenv import load_dotenv
load_dotenv()

from modules.nlu.engine import NLUEngine

# Bảng màu Terminal
class C:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'
    DIM = '\033[2m'

def main():
    # Đảm bảo UTF-8 cho Windows Terminal
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print(f"{C.CYAN}{'='*60}{C.RESET}")
    print(f"{C.CYAN}🤖 TEST NLU REWRITING (TƯƠNG TÁC TRỰC TIẾP){C.RESET}")
    print(f"{C.DIM}Gõ câu hỏi của sếp vào đây. Gõ 'exit' để thoát.{C.RESET}")
    print(f"{C.CYAN}{'='*60}{C.RESET}")

    nlu = NLUEngine()
    chat_history = []

    while True:
        try:
            question = input(f"\n{C.GREEN}Sếp hỏi:{C.RESET} ")
            if question.lower().strip() in ['exit', 'quit']:
                print("Tạm biệt sếp! 👋")
                break
            
            if not question.strip():
                continue

            print(f"{C.DIM}⏳ NLU đang suy nghĩ...{C.RESET}")
            rewritten = nlu.rewrite_question(question, chat_history)
            
            print(f"{C.YELLOW}✨ AI Viết lại:{C.RESET} {rewritten}")
            
            # Lưu lịch sử chat giả lập
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": f"(Giả lập AI trả lời cho câu: {rewritten})"})
            
        except KeyboardInterrupt:
            print("\nTạm biệt sếp! 👋")
            break
        except Exception as e:
            print(f"Lỗi: {e}")

if __name__ == "__main__":
    main()
