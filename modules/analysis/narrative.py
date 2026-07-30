"""
NARRATIVE GENERATOR — AI Viết Nhận Xét Tự Động
Nhận DataFrame + câu hỏi → Gọi Gemini Flash → Trả về đoạn nhận xét markdown.

Ví dụ output:
  📊 Doanh thu Q4/2025 đạt **12.5 tỷ VNĐ**, tăng 45% so với Q3.
  Tháng 12 là tháng đỉnh cao nhất (5.1 tỷ), chủ yếu nhờ chiến dịch Black Friday.
  ⚠️ Tháng 3 chỉ đạt 190 triệu — cần xem lại chiến lược marketing.
"""
import os
import yaml
import pandas as pd
from typing import Optional
from core.logger import get_logger
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Đọc prompt từ file YAML 1 lần duy nhất
_PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompts.yaml")
try:
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        _PROMPTS = yaml.safe_load(f)
except Exception as e:
    logger.error(f"NarrativeGenerator: Không thể đọc prompts.yaml: {e}")
    _PROMPTS = {}


class NarrativeGenerator:
    """
    AI viết nhận xét dữ liệu tự động.
    Phân tích DataFrame kết quả và tạo insight bằng ngôn ngữ tự nhiên (tiếng Việt).
    """

    def __init__(self):
        self.llm = LLMProvider.get_nlu_llm()  # Dùng chung Gemini Flash với NLU

    def generate(self, df: pd.DataFrame, question: str, intent: str = "GENERAL", stat_insights: dict = None) -> Optional[str]:
        """
        Entry point chính — Sinh nhận xét AI từ dữ liệu.

        Args:
            df: DataFrame kết quả từ SQL (đã lọc cột CLS-masked)
            question: Câu hỏi gốc của user
            intent: NLU Intent (TREND, RANKING, COMPARISON...)
            stat_insights: Kết quả từ StatisticalAnalyzer (outliers, trend, pareto...)

        Returns:
            str: Đoạn nhận xét markdown, hoặc None nếu lỗi
        """
        # Không sinh nhận xét cho kết quả quá nhỏ hoặc quá lớn
        if df is None or df.empty:
            return None
        if len(df) > 100:
            logger.info("NarrativeGenerator: Dữ liệu > 100 dòng, bỏ qua narrative (quá dài).")
            return None

        # Chuẩn bị thông tin gửi cho Gemini
        data_summary = self._build_data_summary(df)
        stats_summary = self._build_stats_summary(df)

        # Lấy prompt template
        prompt_template = _PROMPTS.get("narrative_prompt", "")
        if not prompt_template:
            logger.warning("NarrativeGenerator: Không tìm thấy narrative_prompt. Bỏ qua.")
            return None

        # Điền biến vào prompt
        stat_text = self._format_stat_insights(stat_insights) if stat_insights else "Không có."
        prompt = prompt_template.format(
            question=question,
            intent=intent,
            chart_type=intent,
            data_summary=data_summary,
            stats_summary=stats_summary,
            row_count=len(df),
            statistical_insights=stat_text
        )

        # Gọi Gemini Flash
        try:
            logger.info(f"NarrativeGenerator: Đang sinh nhận xét cho câu: '{question[:50]}...'")
            response = self.llm.invoke(prompt)
            narrative = response.content.strip()

            # Loại bỏ markdown code block nếu Gemini trả về bọc ```
            if narrative.startswith("```"):
                lines = narrative.split("\n")
                narrative = "\n".join(lines[1:-1]) if len(lines) > 2 else narrative

            if narrative and len(narrative) > 10:
                logger.info(f"NarrativeGenerator: Đã sinh nhận xét ({len(narrative)} ký tự).")
                return narrative
            else:
                logger.warning("NarrativeGenerator: Nhận xét quá ngắn, bỏ qua.")
                return None

        except Exception as e:
            logger.error(f"NarrativeGenerator: Lỗi gọi Gemini: {e}. Bỏ qua narrative.")
            return None

    def _build_data_summary(self, df: pd.DataFrame, max_rows: int = 10) -> str:
        """Tạo bản tóm tắt dữ liệu để gửi Gemini (tối đa 10 dòng)."""
        sample = df.head(max_rows)
        return sample.to_string(index=False)

    def _build_stats_summary(self, df: pd.DataFrame) -> str:
        """Tạo thống kê nhanh cho các cột số."""
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0:
            return "Không có cột số nào."

        stats_parts = []
        for col in num_cols:
            total = df[col].sum()
            avg = df[col].mean()
            max_val = df[col].max()
            min_val = df[col].min()
            stats_parts.append(
                f"  - {col}: Tổng={total:,.0f} | Trung bình={avg:,.0f} | "
                f"Cao nhất={max_val:,.0f} | Thấp nhất={min_val:,.0f}"
            )
        return "\n".join(stats_parts)

    def _format_stat_insights(self, stat: dict) -> str:
        """Format kết quả StatisticalAnalyzer thành text cho Gemini."""
        parts = []

        # Outliers
        outliers = stat.get("outliers", [])
        if outliers:
            items = []
            for o in outliers[:5]:  # Max 5 outliers
                items.append(f"    • {o['label']}: {o['column']}={o['value']:,.0f} ({o['direction']})")
            parts.append("⚠️ Bất thường phát hiện:\n" + "\n".join(items))

        # Trend
        trend = stat.get("trend", {})
        if trend:
            lines = [f"  - Xu hướng chung: {trend.get('trend_direction', 'N/A')}"]
            if trend.get('total_growth_pct') is not None:
                lines.append(f"  - Tăng trưởng tổng: {trend['total_growth_pct']}%")
            if trend.get('mom_avg') is not None:
                lines.append(f"  - Tăng trưởng trung bình mỗi kỳ: {trend['mom_avg']}%")
            if trend.get('consecutive_growth', 0) >= 3:
                lines.append(f"  - Đã tăng trưởng liên tiếp {trend['consecutive_growth']} kỳ")
            if trend.get('consecutive_decline', 0) >= 3:
                lines.append(f"  - Đã suy giảm liên tiếp {trend['consecutive_decline']} kỳ")
            parts.append("📈 Phân tích xu hướng:\n" + "\n".join(lines))

        # Pareto
        pareto = stat.get("pareto", {})
        if pareto:
            p_text = (f"  - {int(pareto['items_pct'])}% hạng mục chiếm 80% tổng giá trị"
                      f" ({'\u2714 Đúng quy tắc Pareto' if pareto.get('is_pareto') else 'Không theo Pareto'})")
            p_text += f"\n  - Đứng đầu: {pareto.get('top_item_label', '?')} chiếm {pareto.get('top_item_share_pct', 0)}%"
            parts.append("🎯 Phân tích Pareto (80/20):\n" + p_text)

        # Forecast
        forecast = stat.get("forecast", {})
        if forecast:
            f_text = (f"  - Dự báo kỳ tiếp theo: {forecast.get('forecast_next', 0):,.0f}"
                      f" (độ tin cậy: {forecast.get('confidence', '?')}, R²={forecast.get('r_squared', 0)})")
            f_text += f"\n  - Mỗi kỳ thay đổi trung bình: {forecast.get('trend_per_period', 0):+,.0f}"
            parts.append("🔮 Dự báo:\n" + f_text)

        return "\n".join(parts) if parts else "Không có insight thống kê đặc biệt."