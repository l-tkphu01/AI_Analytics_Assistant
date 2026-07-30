"""
VIZ RECOMMENDER — AI Chọn Biểu Đồ Thông Minh (Gemini Flash)
Nhận DataFrame + câu hỏi → Gọi Gemini Flash → Trả về ChartConfig JSON.

Cơ chế Fallback:
  - Gemini trả JSON hợp lệ → Dùng luôn
  - Gemini trả JSON lỗi → Parse lại bằng regex
  - Gemini timeout/crash → Fallback về Bar Chart
"""
import json
import re
import yaml
import os
import pandas as pd
from typing import Dict, Any, Optional
from core.logger import get_logger
from core.llm_providers import LLMProvider

logger = get_logger(__name__)

# Đọc prompt từ file YAML 1 lần duy nhất
_PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "prompts.yaml")
try:
    with open(_PROMPTS_PATH, "r", encoding="utf-8") as f:
        _PROMPTS = yaml.safe_load(f)
except Exception as e:
    logger.error(f"VizRecommender: Không thể đọc prompts.yaml: {e}")
    _PROMPTS = {}


class VizRecommender:
    """
    Bộ não AI đề xuất biểu đồ.
    Gọi Gemini Flash phân tích cấu trúc dữ liệu + câu hỏi → Chọn loại biểu đồ phù hợp nhất.
    """

    # Danh sách chart_type hợp lệ (để validate output của Gemini)
    VALID_CHART_TYPES = {
        "bar", "horizontal_bar", "line", "pie", "kpi_card",
        "stacked_bar", "grouped_bar", "area", "scatter", "heatmap",
        "treemap", "waterfall"
    }

    def __init__(self):
        self.llm = LLMProvider.get_nlu_llm()  # Dùng chung Gemini Flash với NLU

    def suggest(self, df: pd.DataFrame, question: str, intent: str = "GENERAL") -> Dict[str, Any]:
        """
        Entry point chính.
        
        Args:
            df: DataFrame kết quả từ SQL
            question: Câu hỏi gốc của user
            intent: NLU Intent (TREND, RANKING, COMPARISON...)
            
        Returns:
            ChartConfig dict: {chart_type, x_column, y_column, color_column, title, reason}
        """
        # Trường hợp đặc biệt: Kết quả chỉ có 1 dòng 1 cột số → KPI Card ngay
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(df) == 1 and len(num_cols) == 1:
            logger.info("VizRecommender: Kết quả 1 dòng 1 cột số → KPI Card.")
            return {
                "chart_type": "kpi_card",
                "x_column": df.columns[0],
                "y_column": num_cols[0],
                "color_column": None,
                "title": question,
                "reason": "Kết quả chỉ có 1 con số duy nhất, hiển thị dạng KPI Card."
            }

        # Trường hợp đặc biệt: Dữ liệu chỉ toàn text, không có số → Không vẽ
        if len(num_cols) == 0:
            logger.info("VizRecommender: Không có cột số nào → Không vẽ biểu đồ.")
            return {"chart_type": "none", "reason": "Dữ liệu không có cột số để vẽ biểu đồ."}

        # Chuẩn bị thông tin gửi cho Gemini
        columns_info = self._build_columns_info(df)
        sample_data = self._build_sample_data(df, max_rows=5)

        # Lấy prompt template
        prompt_template = _PROMPTS.get("viz_recommender_prompt", "")
        if not prompt_template:
            logger.warning("VizRecommender: Không tìm thấy viz_recommender_prompt trong prompts.yaml. Fallback Bar Chart.")
            return self._fallback_bar(df, question)

        # Điền biến vào prompt
        prompt = prompt_template.format(
            question=question,
            intent=intent,
            columns_info=columns_info,
            sample_data=sample_data
        )

        # Gọi Gemini Flash
        try:
            logger.info(f"VizRecommender: Đang gọi Gemini Flash để chọn biểu đồ cho câu: '{question[:50]}...'")
            response = self.llm.invoke(prompt)
            raw_text = response.content.strip()
            
            # Parse JSON từ response
            chart_config = self._parse_json_response(raw_text)
            
            if chart_config and chart_config.get("chart_type") in self.VALID_CHART_TYPES:
                # Validate x_column và y_column có tồn tại trong DataFrame
                chart_config = self._validate_columns(chart_config, df)
                logger.info(f"VizRecommender: AI chọn '{chart_config['chart_type']}' — {chart_config.get('reason', '')}")
                return chart_config
            else:
                logger.warning(f"VizRecommender: AI trả chart_type không hợp lệ: '{chart_config}'. Fallback Bar Chart.")
                return self._fallback_bar(df, question)

        except Exception as e:
            logger.error(f"VizRecommender: Lỗi gọi Gemini: {e}. Fallback Bar Chart.")
            return self._fallback_bar(df, question)

    def _build_columns_info(self, df: pd.DataFrame) -> str:
        """Tạo mô tả cột + kiểu dữ liệu để gửi cho Gemini."""
        info_parts = []
        for col in df.columns:
            dtype = str(df[col].dtype)
            unique_count = df[col].nunique()
            if "int" in dtype or "float" in dtype:
                col_type = "Số (Number)"
            elif "datetime" in dtype:
                col_type = "Thời gian (DateTime)"
            else:
                col_type = f"Chữ (Text, {unique_count} giá trị khác nhau)"
            info_parts.append(f"  - {col}: {col_type}")
        return "\n".join(info_parts)

    def _build_sample_data(self, df: pd.DataFrame, max_rows: int = 5) -> str:
        """Lấy 5 dòng đầu tiên để gửi cho Gemini."""
        sample = df.head(max_rows)
        return sample.to_string(index=False)

    def _parse_json_response(self, raw_text: str) -> Optional[Dict]:
        """Parse JSON từ response của Gemini (có xử lý markdown code block)."""
        # Thử parse trực tiếp
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Thử tìm JSON trong markdown code block ```json ... ```
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Thử tìm JSON object bất kỳ trong text
        json_match = re.search(r'\{[^{}]*"chart_type"[^{}]*\}', raw_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"VizRecommender: Không parse được JSON từ Gemini response: {raw_text[:200]}")
        return None

    def _validate_columns(self, config: dict, df: pd.DataFrame) -> dict:
        """Validate x_column và y_column có thực sự tồn tại trong DataFrame."""
        df_cols = list(df.columns)
        df_cols_lower = [c.lower() for c in df_cols]
        
        # Validate x_column
        x_col = config.get("x_column", "")
        if x_col not in df_cols:
            # Thử tìm case-insensitive
            if x_col.lower() in df_cols_lower:
                config["x_column"] = df_cols[df_cols_lower.index(x_col.lower())]
            else:
                # Fallback: Dùng cột text đầu tiên
                cat_cols = df.select_dtypes(include=["object", "string"]).columns
                config["x_column"] = cat_cols[0] if len(cat_cols) > 0 else df_cols[0]

        # Validate y_column
        y_col = config.get("y_column", "")
        if y_col not in df_cols:
            if y_col.lower() in df_cols_lower:
                config["y_column"] = df_cols[df_cols_lower.index(y_col.lower())]
            else:
                # Fallback: Dùng cột số đầu tiên
                num_cols = df.select_dtypes(include=["number"]).columns
                config["y_column"] = num_cols[0] if len(num_cols) > 0 else df_cols[-1]

        # Validate color_column
        color_col = config.get("color_column")
        if color_col and color_col not in df_cols:
            config["color_column"] = None

        return config

    def _fallback_bar(self, df: pd.DataFrame, question: str) -> dict:
        """Fallback an toàn: Luôn trả về Bar Chart hợp lệ."""
        cat_cols = df.select_dtypes(include=["object", "string"]).columns
        num_cols = df.select_dtypes(include=["number"]).columns

        x_col = cat_cols[0] if len(cat_cols) > 0 else df.columns[0]
        y_col = num_cols[0] if len(num_cols) > 0 else df.columns[-1]

        # Nếu > 10 dòng, dùng horizontal bar để tránh nhãn đè nhau
        chart_type = "horizontal_bar" if len(df) > 10 else "bar"

        return {
            "chart_type": chart_type,
            "x_column": x_col,
            "y_column": y_col,
            "color_column": None,
            "title": question[:60],
            "reason": "Fallback tự động — AI không thể phân tích, dùng Bar Chart mặc định."
        }