"""
CHART ENGINE — Bộ Sinh Biểu Đồ Plotly (12 loại) [v2.0 — Premium Visual]
Nhận ChartConfig từ AI Recommender → Render biểu đồ Plotly tương ứng.
Có cơ chế Fallback 3 Lớp: Không bao giờ crash!

Nâng cấp v2.0:
  ✅ Format số lớn: 2,150,000,000 → "2.15 tỷ"
  ✅ Data labels trên mỗi cột/đường
  ✅ Hover tooltip chi tiết + format tiền VNĐ
  ✅ Gridlines ngang mờ giúp đọc dữ liệu dễ hơn
  ✅ Bar Chart sắp xếp theo giá trị giảm dần
  ✅ Màu sắc Premium + border radius

Các loại biểu đồ:
  Cốt lõi:   bar, horizontal_bar, line, pie, kpi_card
  Nâng cao:  stacked_bar, grouped_bar, area, scatter, heatmap
  Bonus:     treemap, waterfall
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from core.logger import get_logger

logger = get_logger(__name__)

# ============================================================
# BẢNG MÀU THỐNG NHẤT (Premium, hiện đại)
# ============================================================
BRAND_COLORS = [
    "#6366F1",  # Indigo
    "#8B5CF6",  # Violet
    "#EC4899",  # Pink
    "#F59E0B",  # Amber
    "#10B981",  # Emerald
    "#3B82F6",  # Blue
    "#EF4444",  # Red
    "#14B8A6",  # Teal
    "#F97316",  # Orange
    "#A855F7",  # Purple
    "#06B6D4",  # Cyan
    "#84CC16",  # Lime
]

CHART_LAYOUT = dict(
    font=dict(family="Inter, sans-serif", size=13, color="#334155"),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=50, r=30, t=60, b=50),
    legend=dict(
        orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
        bgcolor="rgba(255,255,255,0.8)", bordercolor="#E2E8F0", borderwidth=1,
        font=dict(size=11)
    ),
)


# ============================================================
# UTILITY: Format số lớn cho dễ đọc (dùng chung toàn bộ charts)
# ============================================================
def _format_vnd(value):
    """Format số sang dạng tỷ/triệu gọn."""
    if not isinstance(value, (int, float)):
        return str(value)
    abs_val = abs(value)
    if abs_val >= 1_000_000_000:
        return f"{value/1_000_000_000:,.2f} tỷ"
    elif abs_val >= 1_000_000:
        return f"{value/1_000_000:,.1f} tr"
    elif abs_val >= 1_000:
        return f"{value:,.0f}"
    else:
        return f"{value:,.2f}"


def _apply_yaxis_format(fig):
    """Format trục Y cho số lớn + thêm gridlines ngang mờ."""
    fig.update_yaxes(
        tickformat=",.",
        gridcolor="rgba(148, 163, 184, 0.15)",
        gridwidth=1,
        zeroline=True,
        zerolinecolor="rgba(148, 163, 184, 0.3)",
    )
    fig.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.08)",
    )
    return fig


def _add_data_labels(fig, df, y_col):
    """Thêm data label trên mỗi cột/điểm (format gọn)."""
    if y_col in df.columns:
        labels = [_format_vnd(v) for v in df[y_col]]
        fig.update_traces(
            text=labels,
            textposition="outside",
            textfont=dict(size=10, color="#475569"),
            cliponaxis=False
        )
    return fig


def _build_hover_template(x_name, y_name, extra=None):
    """Tạo hover tooltip đẹp với format VNĐ."""
    parts = [
        f"<b>%{{x}}</b><br>",
        f"{y_name}: <b>%{{y:,.0f}}</b> VNĐ",
    ]
    if extra:
        parts.append(f"<br>{extra}: %{{customdata[0]}}")
    parts.append("<extra></extra>")
    return "".join(parts)


class ChartEngine:
    """
    Bộ máy vẽ biểu đồ trung tâm.
    Sử dụng: ChartEngine.render(chart_config, df) → plotly.Figure hoặc dict (KPI)
    """

    # Registry: Ánh xạ chart_type → hàm vẽ tương ứng
    _REGISTRY = {}

    @classmethod
    def register(cls, chart_type: str):
        """Decorator đăng ký hàm vẽ vào registry."""
        def wrapper(func):
            cls._REGISTRY[chart_type] = func
            return func
        return wrapper

    @classmethod
    def render(cls, chart_config: dict, df: pd.DataFrame):
        """
        Entry point chính — Cơ chế Fallback 3 Lớp.
        
        Lớp 1: Tìm hàm vẽ tương ứng → Vẽ luôn
        Lớp 2: Không tìm thấy / Lỗi → Fallback về Bar Chart
        Lớp 3: Log cảnh báo chi tiết
        """
        if df is None or df.empty:
            logger.warning("ChartEngine: DataFrame rỗng, không vẽ biểu đồ.")
            return None

        chart_type = chart_config.get("chart_type", "bar")
        render_func = cls._REGISTRY.get(chart_type)

        try:
            if render_func:
                # ✅ Lớp 1: Có hàm tương ứng → Vẽ luôn
                return render_func(chart_config, df)
            else:
                # ⚠️ Lớp 2 + 3: Fallback về Bar Chart + Log cảnh báo
                logger.warning(f"ChartEngine: Chart type '{chart_type}' chưa được hỗ trợ, đã dùng Bar Chart thay thế.")
                return cls._REGISTRY["bar"](chart_config, df)

        except Exception as e:
            # ⚠️ Lớp 2 + 3: Lỗi bất kỳ → Fallback về Bar Chart
            logger.error(f"ChartEngine: Lỗi khi vẽ '{chart_type}': {e}. Fallback về Bar Chart.")
            try:
                return cls._REGISTRY["bar"](chart_config, df)
            except Exception as e2:
                logger.error(f"ChartEngine: Fallback Bar Chart cũng lỗi: {e2}. Bỏ qua biểu đồ.")
                return None

    @staticmethod
    def _apply_layout(fig, title: str):
        """Áp dụng theme thống nhất cho mọi biểu đồ."""
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=16, color="#1E293B", family="Inter, sans-serif"),
                x=0.02,  # Canh trái cho chuyên nghiệp
            ),
            **CHART_LAYOUT
        )
        _apply_yaxis_format(fig)
        return fig


# ============================================================
# 🔴 NHÓM CỐT LÕI (5 loại)
# ============================================================

@ChartEngine.register("bar")
def create_bar_chart(config: dict, df: pd.DataFrame):
    """Biểu đồ cột dọc — So sánh giá trị giữa các danh mục."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column")
    title = config.get("title", f"{y} theo {x}")

    # Sắp xếp theo giá trị giảm dần (nếu không có color grouping)
    if not color and y in df.columns:
        df = df.sort_values(y, ascending=False)

    # Data labels trên mỗi cột
    labels = [_format_vnd(v) for v in df[y]] if y in df.columns else []
    fig = px.bar(df, x=x, y=y, color=color or x, text=labels,
                 color_discrete_sequence=BRAND_COLORS, title=title)
    
    fig.update_traces(
        textposition="outside",
        textfont=dict(size=10, color="#475569"),
        cliponaxis=False,
        hovertemplate=f"<b>%{{x}}</b><br>{y}: <b>%{{y:,.0f}}</b> VNĐ<extra></extra>"
    )
    fig.update_layout(showlegend=False if not color else True)
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("horizontal_bar")
def create_horizontal_bar(config: dict, df: pd.DataFrame):
    """Biểu đồ thanh ngang — Tránh nhãn đè nhau khi > 10 mục hoặc tên dài."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    title = config.get("title", f"{y} theo {x}")

    # Sắp xếp tăng dần (vì trục Y đảo ngược → hiển thị từ lớn đến nhỏ)
    if y in df.columns:
        df = df.sort_values(y, ascending=True)

    # Data labels bên phải thanh
    labels = [_format_vnd(v) for v in df[y]] if y in df.columns else []
    fig = px.bar(df, x=y, y=x, orientation="h", color=x, text=labels,
                 color_discrete_sequence=BRAND_COLORS, title=title)
    
    fig.update_traces(
        textposition="outside",
        textfont=dict(size=10, color="#475569"),
        cliponaxis=False,
        hovertemplate=f"<b>%{{y}}</b><br>{y}: <b>%{{x:,.0f}}</b> VNĐ<extra></extra>"
    )
    fig.update_layout(showlegend=False)
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("line")
def create_line_chart(config: dict, df: pd.DataFrame):
    """Biểu đồ đường — Xu hướng theo thời gian."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column")
    title = config.get("title", f"Xu hướng {y} theo {x}")

    fig = px.line(df, x=x, y=y, color=color, markers=True,
                  color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        line=dict(width=2.5),
        marker=dict(size=7),
        hovertemplate=f"<b>%{{x}}</b><br>{y}: <b>%{{y:,.0f}}</b> VNĐ<extra></extra>"
    )
    # Thêm data labels cho điểm dữ liệu (chỉ khi ≤ 15 điểm để tránh rối)
    if len(df) <= 15 and y in df.columns:
        labels = [_format_vnd(v) for v in df[y]]
        fig.update_traces(text=labels, textposition="top center", textfont=dict(size=9, color="#64748B"))
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("pie")
def create_pie_chart(config: dict, df: pd.DataFrame):
    """Biểu đồ tròn Donut — Cơ cấu tỷ lệ phần trăm."""
    names = config.get("x_column", df.columns[0])
    values = config.get("y_column", df.columns[-1])
    title = config.get("title", f"Cơ cấu {values}")

    fig = px.pie(df, names=names, values=values, hole=0.45,
                 color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        textinfo="percent+label",
        textfont_size=12,
        pull=[0.03] * len(df),  # Tách nhẹ mỗi phần để đẹp hơn
        hovertemplate="<b>%{label}</b><br>Giá trị: <b>%{value:,.0f}</b> VNĐ<br>Tỷ lệ: <b>%{percent}</b><extra></extra>"
    )
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("kpi_card")
def create_kpi_card(config: dict, df: pd.DataFrame):
    """
    Thẻ KPI — Khi kết quả chỉ có 1 con số duy nhất.
    Trả về dict thay vì Figure (UI sẽ render bằng st.metric).
    """
    # Tìm cột số đầu tiên
    num_cols = df.select_dtypes(include=["number"]).columns
    if len(num_cols) > 0:
        value = df[num_cols[0]].iloc[0]
        label = config.get("title", num_cols[0])
    else:
        value = df.iloc[0, 0]
        label = config.get("title", df.columns[0])

    formatted = _format_vnd(value)

    return {
        "type": "kpi_card",
        "label": label,
        "value": formatted,
        "raw_value": value,
        "reason": config.get("reason", "")
    }


# ============================================================
# 🟡 NHÓM NÂNG CAO (5 loại)
# ============================================================

@ChartEngine.register("stacked_bar")
def create_stacked_bar(config: dict, df: pd.DataFrame):
    """Biểu đồ cột chồng — Cơ cấu bên trong từng nhóm."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column", df.columns[1] if len(df.columns) > 2 else None)
    title = config.get("title", f"{y} theo {x}")

    fig = px.bar(df, x=x, y=y, color=color, barmode="stack",
                 color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        hovertemplate=f"<b>%{{x}}</b><br>{y}: <b>%{{y:,.0f}}</b> VNĐ<extra></extra>"
    )
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("grouped_bar")
def create_grouped_bar(config: dict, df: pd.DataFrame):
    """Biểu đồ cột ghép nhóm — So sánh nhiều metric song song."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column", df.columns[1] if len(df.columns) > 2 else None)
    title = config.get("title", f"So sánh {y} theo {x}")

    fig = px.bar(df, x=x, y=y, color=color, barmode="group",
                 color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        hovertemplate=f"<b>%{{x}}</b><br>{y}: <b>%{{y:,.0f}}</b> VNĐ<extra></extra>"
    )
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("area")
def create_area_chart(config: dict, df: pd.DataFrame):
    """Biểu đồ vùng — Xu hướng tích lũy theo thời gian."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column")
    title = config.get("title", f"Xu hướng tích lũy {y}")

    fig = px.area(df, x=x, y=y, color=color,
                  color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        line=dict(width=2),
        hovertemplate=f"<b>%{{x}}</b><br>{y}: <b>%{{y:,.0f}}</b> VNĐ<extra></extra>"
    )
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("scatter")
def create_scatter_chart(config: dict, df: pd.DataFrame):
    """Biểu đồ phân tán — Tương quan giữa 2 biến số."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column")
    title = config.get("title", f"Tương quan {x} vs {y}")

    fig = px.scatter(df, x=x, y=y, color=color, size_max=15,
                     color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        marker=dict(size=10, opacity=0.75, line=dict(width=1, color="#FFFFFF")),
        hovertemplate=f"<b>{x}:</b> %{{x:,.0f}}<br><b>{y}:</b> %{{y:,.0f}}<extra></extra>"
    )
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("heatmap")
def create_heatmap(config: dict, df: pd.DataFrame):
    """Bản đồ nhiệt — Ma trận 2 chiều (VD: Doanh thu theo Tháng × Khu vực)."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[1] if len(df.columns) > 1 else df.columns[0])
    z_col = config.get("color_column") or df.select_dtypes(include=["number"]).columns[0] if len(df.select_dtypes(include=["number"]).columns) > 0 else df.columns[-1]
    title = config.get("title", f"Heatmap {z_col}")

    # Pivot data thành ma trận nếu cần
    try:
        pivot_df = df.pivot_table(index=y, columns=x, values=z_col, aggfunc="sum").fillna(0)
        fig = px.imshow(pivot_df, text_auto=True, aspect="auto",
                        color_continuous_scale="RdYlBu_r", title=title)
    except Exception:
        # Nếu pivot lỗi, vẽ density heatmap thay thế
        fig = px.density_heatmap(df, x=x, y=y, title=title,
                                  color_continuous_scale="RdYlBu_r")
    
    fig.update_layout(coloraxis_colorbar=dict(title=z_col, tickformat=","))
    return ChartEngine._apply_layout(fig, title)


# ============================================================
# 🟢 NHÓM BONUS (2 loại)
# ============================================================

@ChartEngine.register("treemap")
def create_treemap(config: dict, df: pd.DataFrame):
    """Bản đồ cây — Phân tầng dữ liệu (hierarchical)."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    color = config.get("color_column")
    title = config.get("title", f"Treemap {y}")

    path_cols = [x]
    if color and color != x and color in df.columns:
        path_cols = [color, x]

    fig = px.treemap(df, path=path_cols, values=y,
                     color_discrete_sequence=BRAND_COLORS, title=title)
    fig.update_traces(
        textinfo="label+value+percent root",
        hovertemplate="<b>%{label}</b><br>Giá trị: %{value:,.0f} VNĐ<br>Tỷ lệ: %{percentRoot:.1%}<extra></extra>"
    )
    return ChartEngine._apply_layout(fig, title)


@ChartEngine.register("waterfall")
def create_waterfall(config: dict, df: pd.DataFrame):
    """Biểu đồ thác nước — Phân tích tài chính cộng/trừ."""
    x = config.get("x_column", df.columns[0])
    y = config.get("y_column", df.columns[-1])
    title = config.get("title", f"Waterfall {y}")

    fig = go.Figure(go.Waterfall(
        name=y,
        orientation="v",
        x=df[x].tolist(),
        y=df[y].tolist(),
        connector=dict(line=dict(color="#94A3B8", width=1.5)),
        increasing=dict(marker=dict(color="#10B981")),
        decreasing=dict(marker=dict(color="#EF4444")),
        totals=dict(marker=dict(color="#6366F1")),
        textposition="outside",
        text=[_format_vnd(v) for v in df[y]],
        textfont=dict(size=10, color="#475569"),
    ))
    return ChartEngine._apply_layout(fig, title)