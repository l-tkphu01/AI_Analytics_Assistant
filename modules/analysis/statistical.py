"""
STATISTICAL ANALYSIS ENGINE — Phân tích thống kê tự động
Module toán học thuần túy (không gọi AI) — Cung cấp insight chính xác cho Narrative AI.

4 Tính năng chính:
  1. Outlier Detection (Z-score)
  2. Trend & Growth (MoM, YoY, CAGR)
  3. Pareto Analysis (Quy tắc 80/20)
  4. Basic Forecasting (Linear Regression)
"""
import numpy as np
import pandas as pd
from typing import Optional
from core.logger import get_logger

logger = get_logger(__name__)


class StatisticalAnalyzer:
    """
    Bộ phân tích thống kê — Chạy thuần toán học, không gọi LLM.
    Input: DataFrame + NLU intent
    Output: dict chứa các insight đã tính toán sẵn
    """

    def analyze(self, df: pd.DataFrame, intent: str = "GENERAL") -> dict:
        """
        Entry point — Chạy tất cả phân tích phù hợp với intent.

        Returns:
            dict với các key: outliers, trend, pareto, forecast, basic_stats
        """
        if df is None or df.empty:
            return {}

        results = {}

        try:
            # Luôn chạy: Thống kê cơ bản
            results["basic_stats"] = self._basic_stats(df)
        except Exception as e:
            logger.warning(f"StatAnalyzer: Lỗi basic_stats: {e}")

        try:
            # Phát hiện outlier cho mọi intent có cột số
            results["outliers"] = self._detect_outliers(df)
        except Exception as e:
            logger.warning(f"StatAnalyzer: Lỗi outlier detection: {e}")

        try:
            # Trend + Growth: Chỉ chạy khi intent liên quan xu hướng
            if intent in ("TREND", "COMPARISON", "AGGREGATION"):
                results["trend"] = self._analyze_trend(df)
        except Exception as e:
            logger.warning(f"StatAnalyzer: Lỗi trend analysis: {e}")

        try:
            # Pareto: Chỉ chạy khi xếp hạng hoặc tổng hợp
            if intent in ("RANKING", "AGGREGATION", "COMPARISON"):
                results["pareto"] = self._pareto_analysis(df)
        except Exception as e:
            logger.warning(f"StatAnalyzer: Lỗi pareto analysis: {e}")

        try:
            # Forecast: Chỉ khi có dữ liệu theo thời gian
            if intent == "TREND" and len(df) >= 3:
                results["forecast"] = self._basic_forecast(df)
        except Exception as e:
            logger.warning(f"StatAnalyzer: Lỗi forecast: {e}")

        logger.info(f"StatAnalyzer: Hoàn tất phân tích ({', '.join(results.keys())})")
        return results

    # ================================================================
    # 1. THỐNG KÊ CƠ BẢN
    # ================================================================
    def _basic_stats(self, df: pd.DataFrame) -> dict:
        """Tính các chỉ số thống kê cơ bản cho mọi cột số."""
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0:
            return {}

        stats = {}
        for col in num_cols:
            series = df[col].dropna()
            if series.empty:
                continue
            stats[col] = {
                "count": int(len(series)),
                "sum": float(series.sum()),
                "mean": float(series.mean()),
                "median": float(series.median()),
                "std": float(series.std()) if len(series) > 1 else 0,
                "min": float(series.min()),
                "max": float(series.max()),
                "range": float(series.max() - series.min()),
                "cv": float(series.std() / series.mean() * 100) if series.mean() != 0 and len(series) > 1 else 0,
            }
        return stats

    # ================================================================
    # 2. PHÁT HIỆN BẤT THƯỜNG (Outlier Detection — Z-score + IQR)
    # ================================================================
    def _detect_outliers(self, df: pd.DataFrame) -> list:
        """
        Phát hiện giá trị bất thường bằng phương pháp IQR.
        Trả về danh sách các điểm bất thường kèm giải thích.
        """
        num_cols = df.select_dtypes(include=["number"]).columns
        outliers = []

        for col in num_cols:
            series = df[col].dropna()
            if len(series) < 4:  # Cần ít nhất 4 điểm để tính IQR
                continue

            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1

            if iqr == 0:
                continue

            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr

            # Tìm các dòng có giá trị ngoài biên
            for idx in series.index:
                val = series[idx]
                if val < lower_bound:
                    # Tìm label (giá trị cột đầu tiên không phải số)
                    label = self._get_row_label(df, idx)
                    outliers.append({
                        "column": col,
                        "label": label,
                        "value": float(val),
                        "direction": "thấp bất thường",
                        "threshold": f"< {lower_bound:,.0f}"
                    })
                elif val > upper_bound:
                    label = self._get_row_label(df, idx)
                    outliers.append({
                        "column": col,
                        "label": label,
                        "value": float(val),
                        "direction": "cao bất thường",
                        "threshold": f"> {upper_bound:,.0f}"
                    })

        return outliers

    # ================================================================
    # 3. PHÂN TÍCH XU HƯỚNG & TĂNG TRƯỞNG (Trend & Growth)
    # ================================================================
    def _analyze_trend(self, df: pd.DataFrame) -> dict:
        """
        Tính toán xu hướng: MoM, tăng trưởng tổng thể, biến động.
        Giả định: Dòng đầu tiên = thời gian sớm nhất, dòng cuối = mới nhất.
        """
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0 or len(df) < 2:
            return {}

        # Chọn cột số chính (cột có tổng lớn nhất)
        main_col = max(num_cols, key=lambda c: abs(df[c].sum()))
        series = df[main_col].values

        result = {
            "column": main_col,
            "first_value": float(series[0]),
            "last_value": float(series[-1]),
            "periods": len(series),
        }

        # Tăng trưởng tổng thể (%)
        if series[0] != 0:
            result["total_growth_pct"] = round((series[-1] - series[0]) / abs(series[0]) * 100, 1)
        else:
            result["total_growth_pct"] = None

        # CAGR (Compound Annual Growth Rate) — nếu đủ dữ liệu
        if len(series) > 1 and series[0] > 0 and series[-1] > 0:
            n = len(series) - 1
            result["cagr_per_period"] = round(((series[-1] / series[0]) ** (1 / n) - 1) * 100, 2)

        # Tính MoM (month-over-month) cho từng kỳ
        mom_changes = []
        for i in range(1, len(series)):
            if series[i - 1] != 0:
                change = (series[i] - series[i - 1]) / abs(series[i - 1]) * 100
                mom_changes.append(round(change, 1))

        if mom_changes:
            result["mom_avg"] = round(np.mean(mom_changes), 1)
            result["mom_max"] = max(mom_changes)
            result["mom_min"] = min(mom_changes)
            result["consecutive_growth"] = self._count_consecutive_growth(series)
            result["consecutive_decline"] = self._count_consecutive_decline(series)

        # Xu hướng chung: Dùng hệ số tương quan Pearson
        x = np.arange(len(series))
        if np.std(series) > 0:
            correlation = np.corrcoef(x, series)[0, 1]
            result["trend_correlation"] = round(correlation, 3)
            if correlation > 0.7:
                result["trend_direction"] = "tăng mạnh"
            elif correlation > 0.3:
                result["trend_direction"] = "tăng nhẹ"
            elif correlation > -0.3:
                result["trend_direction"] = "đi ngang"
            elif correlation > -0.7:
                result["trend_direction"] = "giảm nhẹ"
            else:
                result["trend_direction"] = "giảm mạnh"

        return result

    # ================================================================
    # 4. PHÂN TÍCH PARETO (Quy tắc 80/20)
    # ================================================================
    def _pareto_analysis(self, df: pd.DataFrame) -> Optional[dict]:
        """
        Kiểm tra quy tắc 80/20: X% hạng mục chiếm Y% tổng giá trị.
        """
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0 or len(df) < 3:
            return None

        # Chọn cột số chính
        main_col = max(num_cols, key=lambda c: abs(df[c].sum()))
        sorted_vals = df[main_col].sort_values(ascending=False).values

        total = sorted_vals.sum()
        if total == 0:
            return None

        # Tính cumulative %
        cumsum = np.cumsum(sorted_vals)
        cumulative_pct = cumsum / total * 100

        # Tìm bao nhiêu % hạng mục chiếm 80% giá trị
        items_for_80 = 0
        for i, pct in enumerate(cumulative_pct):
            if pct >= 80:
                items_for_80 = i + 1
                break

        if items_for_80 == 0:
            items_for_80 = len(sorted_vals)

        items_pct = round(items_for_80 / len(sorted_vals) * 100, 0)

        # Tìm label của top item
        top_label = self._get_row_label(df, df[main_col].idxmax())

        result = {
            "column": main_col,
            "total_items": len(sorted_vals),
            "items_for_80pct": items_for_80,
            "items_pct": items_pct,
            "top_item_label": top_label,
            "top_item_value": float(sorted_vals[0]),
            "top_item_share_pct": round(sorted_vals[0] / total * 100, 1),
            "is_pareto": items_pct <= 30,  # Đúng Pareto nếu ≤30% hạng mục chiếm 80%
        }

        return result

    # ================================================================
    # 5. DỰ BÁO CƠ BẢN (Linear Regression)
    # ================================================================
    def _basic_forecast(self, df: pd.DataFrame, periods: int = 3) -> Optional[dict]:
        """
        Dự báo đơn giản bằng Linear Regression (y = ax + b).
        Dự báo thêm `periods` kỳ tiếp theo.
        """
        num_cols = df.select_dtypes(include=["number"]).columns
        if len(num_cols) == 0 or len(df) < 3:
            return None

        main_col = max(num_cols, key=lambda c: abs(df[c].sum()))
        y = df[main_col].values.astype(float)
        x = np.arange(len(y))

        # Kiểm tra variance
        if np.std(y) == 0:
            return None

        # Linear Regression: y = a*x + b
        a, b = np.polyfit(x, y, 1)

        # R² (hệ số xác định)
        y_pred = a * x + b
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # Dự báo
        future_x = np.arange(len(y), len(y) + periods)
        future_y = a * future_x + b

        result = {
            "column": main_col,
            "slope": round(float(a), 2),
            "intercept": round(float(b), 2),
            "r_squared": round(float(r_squared), 4),
            "confidence": "cao" if r_squared > 0.7 else ("trung bình" if r_squared > 0.4 else "thấp"),
            "forecast_values": [round(float(v), 0) for v in future_y],
            "forecast_next": round(float(future_y[0]), 0),
            "trend_per_period": round(float(a), 0),
        }

        return result

    # ================================================================
    # UTILS
    # ================================================================
    def _get_row_label(self, df: pd.DataFrame, idx) -> str:
        """Lấy nhãn (label) cho một dòng dữ liệu — dùng cột text đầu tiên."""
        text_cols = df.select_dtypes(include=["object", "category"]).columns
        if len(text_cols) > 0:
            return str(df.loc[idx, text_cols[0]])
        return str(idx)

    def _count_consecutive_growth(self, series) -> int:
        """Đếm số kỳ tăng trưởng liên tiếp gần nhất."""
        count = 0
        for i in range(len(series) - 1, 0, -1):
            if series[i] > series[i - 1]:
                count += 1
            else:
                break
        return count

    def _count_consecutive_decline(self, series) -> int:
        """Đếm số kỳ suy giảm liên tiếp gần nhất."""
        count = 0
        for i in range(len(series) - 1, 0, -1):
            if series[i] < series[i - 1]:
                count += 1
            else:
                break
        return count