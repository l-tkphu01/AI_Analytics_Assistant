# NỘI DUNG CẦN LÀM:
# - Base image: python:3.11-slim
# - Cài ODBC Driver 18 (kết nối Fabric SQL Endpoint)
# - Cài Playwright + Chromium (render PDF)
# - Copy requirements.txt → pip install
# - Copy source code
# - Tạo thư mục data/ (chroma_db, query_cache, exports)
# - Expose port 8000 (FastAPI) + 8501 (Streamlit)
# - CMD: chạy cả uvicorn + streamlit cùng lúc 