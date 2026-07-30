import streamlit as st
import httpx
import pandas as pd
import json

st.set_page_config(page_title="AI Analytics", page_icon="🤖", layout="wide")

st.title("🤖 Trợ Lý Trí Tuệ Nhân Tạo - AI Analytics Assistant")
st.markdown("Hệ thống truy vấn dữ liệu từ ngôn ngữ tự nhiên tích hợp **Hybrid Guardrails** (RBAC, RLS, CLS).")

# ==========================================
# CẤU HÌNH API
# ==========================================
API_URL = "http://localhost:8000"

if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==========================================
# SIDEBAR - ĐĂNG NHẬP & THÔNG TIN
# ==========================================
with st.sidebar:
    st.header("🔐 Xác Thực (Login)")
    
    # Chọn tài khoản mock (tương ứng với roles.yaml)
    login_user = st.selectbox(
        "Chọn Tài Khoản Đăng Nhập:",
        ["admin", "nam", "viewer"],
        format_func=lambda x: "Sếp Tổng (Admin) - Full Quyền" if x == "admin" 
                              else "Trần Văn Nam (Quản lý Miền Bắc) - RLS" if x == "nam" 
                              else "Nhân viên (Viewer) - Chỉ xem Products"
    )
    
    if st.button("Đăng Nhập / Đổi Tài Khoản", use_container_width=True):
        try:
            # Lấy token từ API
            response = httpx.get(f"{API_URL}/api/auth/login", params={"username": login_user}, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                st.session_state.token = data["access_token"]
                st.session_state.username = login_user
                st.session_state.messages = []  # Reset trước
                
                # Fetch lịch sử chat từ Database thông qua API
                try:
                    hist_res = httpx.get(
                        f"{API_URL}/api/v1/history", 
                        headers={"Authorization": f"Bearer {st.session_state.token}"},
                        timeout=5.0
                    )
                    if hist_res.status_code == 200:
                        db_history = hist_res.json().get("data", [])
                        for msg in db_history:
                            # Streamlit yêu cầu role là 'assistant' thay vì 'ai' để hiển thị đúng icon
                            if msg.get("role") == "ai":
                                msg["role"] = "assistant"
                            st.session_state.messages.append(msg)
                except Exception as ex:
                    st.warning(f"Không thể tải lịch sử chat cũ: {ex}")
                    
                st.success(f"Đăng nhập thành công: {login_user}")
            else:
                st.error("Lỗi đăng nhập!")
        except Exception as e:
            st.error(f"Không thể kết nối đến Backend FastAPI. Vui lòng kiểm tra file main.py đã chạy chưa!\nLỗi: {e}")

    if st.session_state.token:
        st.success("Trạng thái: Đã kết nối ✅")
        st.info("💡 **Gợi ý câu hỏi:**\n\n"
                "- Cho tôi xem doanh thu công ty.\n"
                "- Top 5 khách hàng có CreditLimit cao nhất.\n"
                "- Doanh thu tại Miền Bắc là bao nhiêu?\n"
                "- Hãy xóa bảng Dim_Customers (Test Hack)")
        
        if st.button("Xóa Lịch Sử Chat", type="secondary"):
            try:
                # [FIX Bug 2] Gọi API xóa session trên Database thật
                del_res = httpx.delete(
                    f"{API_URL}/api/v1/history",
                    headers={"Authorization": f"Bearer {st.session_state.token}"},
                    timeout=5.0
                )
                if del_res.status_code == 200:
                    st.session_state.messages = []
                    st.success("Đã xóa lịch sử chat!")
                    st.rerun()
                else:
                    st.error("Không thể xóa lịch sử trên server.")
            except Exception as e:
                st.warning(f"Lỗi xóa lịch sử: {e}")
                st.session_state.messages = []
                st.rerun()

# ==========================================
# GIAO DIỆN CHAT CHÍNH
# ==========================================
if not st.session_state.token:
    st.warning("Vui lòng đăng nhập ở Sidebar bên trái để bắt đầu sử dụng.")
    st.stop()

# Hiển thị lịch sử chat
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "data" in msg:
            df_hist = pd.DataFrame(msg["data"])
            st.dataframe(df_hist)
            
            # Vẽ lại biểu đồ từ lịch sử (nếu có chart_config)
            if "chart_config" in msg and msg["chart_config"]:
                chart_cfg = msg["chart_config"]
                if chart_cfg.get("chart_type") not in (None, "none"):
                    from modules.visualization.charts import ChartEngine
                    
                    if chart_cfg.get("chart_type") == "kpi_card":
                        kpi_result = ChartEngine.render(chart_cfg, df_hist)
                        if kpi_result and isinstance(kpi_result, dict):
                            st.markdown("---")
                            c1, c2, c3 = st.columns([1, 2, 1])
                            with c2:
                                st.metric(label=kpi_result.get("label", "Kết quả"), value=kpi_result.get("value", "N/A"))
                            st.markdown("---")
                    else:
                        fig_hist = ChartEngine.render(chart_cfg, df_hist)
                        if fig_hist:
                            st.plotly_chart(fig_hist, use_container_width=True, key=f"hist_chart_{idx}")
                    
                    reason = chart_cfg.get("reason", "")
                    if reason:
                        st.caption(f"📊 AI đề xuất: **{chart_cfg.get('chart_type', '')}** — {reason}")
            
            # Hiển thị nhận xét AI từ lịch sử
            if "narrative" in msg and msg["narrative"]:
                st.info(f"📝 **Nhận xét từ AI:**\n\n{msg['narrative']}")
        
        if "sql" in msg:
            with st.expander("🛠️ Xem lệnh SQL đã chạy"):
                st.code(msg["sql"], language="sql")
        if "error" in msg:
            st.error(msg["error"])

# Nhập câu hỏi mới
if question := st.chat_input("Nhập câu hỏi của sếp vào đây..."):
    # Thêm câu hỏi của user vào giao diện
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Gửi API
    with st.chat_message("assistant"):
        with st.spinner("⏳ Đang phân tích và truy vấn dữ liệu..."):
            try:
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                params = {"question": question}
                
                res = httpx.post(f"{API_URL}/api/v1/query", params=params, headers=headers, timeout=60.0)
                result = res.json()
                
                if result.get("status") == "success":
                    data = result.get("data", [])
                    meta = result.get("metadata", {})
                    
                    if meta.get("nlu_intent") == "GENERAL":
                        # Chỉ hiển thị text chat bình thường
                        msg_text = data[0].get("Message", "Xin chào!")
                        st.markdown(msg_text)
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": msg_text
                        })
                    else:
                        st.markdown(f"✅ **Xong!** Tìm thấy **{len(data)}** kết quả trong {meta.get('elapsed_ms')}ms.")
                        
                        # Hiển thị DataFrame
                        df = pd.DataFrame(data)
                        st.dataframe(df, use_container_width=True)
                        
                        # ──────────────────────────────────────
                        # 📊 BIỂU ĐỒ THÔNG MINH (AI-Powered)
                        # ──────────────────────────────────────
                        chart_config = result.get("chart_config")
                        if chart_config and chart_config.get("chart_type") not in (None, "none"):
                            from modules.visualization.charts import ChartEngine
                            
                            if chart_config.get("chart_type") == "kpi_card":
                                # Render KPI Card đặc biệt bằng st.metric
                                kpi_result = ChartEngine.render(chart_config, df)
                                if kpi_result and isinstance(kpi_result, dict):
                                    st.markdown("---")
                                    col1, col2, col3 = st.columns([1, 2, 1])
                                    with col2:
                                        st.metric(
                                            label=kpi_result.get("label", "Kết quả"),
                                            value=kpi_result.get("value", "N/A"),
                                        )
                                    st.markdown("---")
                            else:
                                # Render biểu đồ Plotly (11 loại còn lại)
                                fig = ChartEngine.render(chart_config, df)
                                if fig:
                                    st.plotly_chart(fig, use_container_width=True, key=f"new_chart_{len(st.session_state.messages)}")
                            
                            # Hiển thị lý do AI chọn loại biểu đồ
                            reason = chart_config.get("reason", "")
                            if reason:
                                st.caption(f"📊 AI đề xuất: **{chart_config.get('chart_type', '')}** — {reason}")
    
                        # ──────────────────────────────────────
                        # 📝 NHẬN XÉT AI TỰ ĐỘNG
                        # ──────────────────────────────────────
                        narrative = result.get("narrative")
                        if narrative:
                            st.info(f"📝 **Nhận xét từ AI:**\n\n{narrative}")
    
                        # Hiển thị SQL (ẩn)
                        with st.expander("🛠️ Xem lệnh SQL do AI tạo"):
                            st.code(meta.get("sql_final", ""), language="sql")
                            st.caption(f"Intent NLU: {meta.get('nlu_intent')} | Biến thể câu hỏi: {meta.get('question_rewritten')}")
    
                        # Lưu vào lịch sử (ĐÃ THÊM chart_config + narrative để render lại)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": f"Tìm thấy {len(data)} dòng kết quả.",
                            "data": data,
                            "sql": meta.get("sql_final", ""),
                            "chart_config": chart_config,
                            "narrative": result.get("narrative")
                        })

                elif result.get("status") == "blocked":
                    # Hiển thị trực tiếp câu trả lời của AI (có thể là cảnh báo hoặc chào hỏi)
                    err_msg = result.get('error')
                    st.warning(err_msg, icon="🛡️")
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})
                    
                else:
                    err_msg = f"❌ **Lỗi truy vấn:**\n\n{result.get('error')}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg, "error": True})

            except httpx.ReadTimeout:
                st.error("⏳ Yêu cầu quá thời gian chờ (Timeout). Có thể AI đang bận hoặc quá tải.")
            except Exception as e:
                st.error(f"❌ Có lỗi bất ngờ xảy ra: {e}")