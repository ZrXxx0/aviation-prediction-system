
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from decimal import Decimal, InvalidOperation
from typing import Optional
from datetime import datetime

import numpy as np
import pandas as pd

# 1) 设置 Django 环境（按你的项目修改）
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AirlinePredictSystem.settings")
import django
django.setup()

from django.db import transaction, close_old_connections
from predict.models import FlightMarketRecord

# ================= 配置 =================
CSV_PATH = Path(r"D:\desk\Airlinepredict\final_data_0729.csv")

WORKERS = 8
BATCH_SIZE = 5000
IGNORE_CONFLICTS = True       # 方案A：遇到唯一键冲突静默跳过
PROGRESS_STEP = 100           # 每写入100条刷新一次进度

# CSV 列名 -> 模型字段名（请保持与CSV一致）
COLUMN_MAP = {
    "YearMonth": "year_month",       # 原始格式如 '2017/3/1'，导入时转为 'YYYY-MM'
    "Origin": "origin",
    "Destination": "destination",
    "Equipment": "equipment",
    "Distance (KM)": "distance_km",
    "International Flight": "international_flight",
    "Equipment_Total_Flights": "equipment_total_flights",
    "Equipment_Total_Seats": "equipment_total_seats",
    "Route_Total_Flights": "route_total_flights",
    "Route_Total_Seats": "route_total_seats",
    "Route_Total_Flight_Time": "route_total_flight_time",
    "Route_Avg_Flight_Time": "route_avg_flight_time",
    "Con Total Est. Pax": "con_total_est_pax",
    "First": "first",
    "Business": "business",
    "Premium": "premium",
    "Full Y": "full_y",
    "Disc Y": "disc_y",
    "Avg yield": "avg_yield",
    "Avg First": "avg_first",
    "Avg Business": "avg_business",
    "Avg Premium": "avg_premium",
    "Avg Full Y": "avg_full_y",
    "Avg Disc Y": "avg_disc_y",
    "Region": "region",
    "Total Est. Pax": "total_est_pax",
    "Local Est. Pax": "local_est_pax",
    "Behind Est. Pax": "behind_est_pax",
    "Bridge Est. Pax": "bridge_est_pax",
    "Beyond Est. Pax": "beyond_est_pax",
    "Avg Fare (USD)": "avg_fare_usd",
    "Local Fare": "local_fare",
    "Behind Fare": "behind_fare",
    "Bridge Fare": "bridge_fare",
    "Beyond Fare": "beyond_fare",
    "O_GDP": "o_gdp",
    "O_Population": "o_population",
    "Third_Industry_x": "third_industry_x",
    "O_Revenue": "o_revenue",
    "O_Retail": "o_retail",
    "O_Labor": "o_labor",
    "O_Air_Traffic": "o_air_traffic",
    "D_GDP": "d_gdp",
    "D_Population": "d_population",
    "Third_Industry_y": "third_industry_y",
    "D_Revenue": "d_revenue",
    "D_Retail": "d_retail",
    "D_Labor": "d_labor",
    "D_Air_Traffic": "d_air_traffic",
}
USECOLS = list(COLUMN_MAP.keys())

# ========= 类型分组（模型里整数已改为 DecimalField）=========
DEC_FIELDS = {
    "distance_km", "equipment_total_flights", "equipment_total_seats",
    "route_total_flights", "route_total_seats",
    "route_total_flight_time", "route_avg_flight_time",
    "con_total_est_pax", "first", "business", "premium", "full_y", "disc_y",
    "avg_yield", "avg_first", "avg_business", "avg_premium", "avg_full_y", "avg_disc_y",
    "total_est_pax", "local_est_pax", "behind_est_pax", "bridge_est_pax", "beyond_est_pax",
    "avg_fare_usd", "local_fare", "behind_fare", "bridge_fare", "beyond_fare",
    "o_gdp", "o_population", "third_industry_x", "o_revenue", "o_retail", "o_labor", "o_air_traffic",
    "d_gdp", "d_population", "third_industry_y", "d_revenue", "d_retail", "d_labor", "d_air_traffic",
}
BOOL_FIELDS = {"international_flight"}
STR_FIELDS  = {"origin", "destination", "equipment", "region"}  # year_month 单独处理

# ----------- 工具函数 -----------
def to_decimal(v: object) -> Optional[Decimal]:
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        try:
            s2 = s.replace(",", "")
            return Decimal(s2)
        except Exception:
            return None

def to_bool(v: object) -> bool:
    if v is None:
        return False
    s = str(v).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    try:
        return bool(int(float(s)))
    except Exception:
        return False

def to_year_month(v: object) -> Optional[str]:
    """
    把原始字符串日期（例如 '2017/3/1' 或 '2017/03/01'）转换为 'YYYY-MM'。
    解析失败返回 None。
    """
    if v is None:
        return None
    s = str(v).strip()
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None
    # 常见形态：YYYY/M/D 或 YYYY/MM/DD
    try:
        dt = datetime.strptime(s, "%Y/%m/%d")
        return dt.strftime("%Y-%m")
    except Exception:
        # 兜底：如果已经是 'YYYY-M' 或 'YYYY-MM'，补零规范化
        if "-" in s:
            parts = s.split("-", 1)
            if len(parts) == 2 and parts[0].isdigit():
                m = "".join(ch for ch in parts[1] if ch.isdigit())  # 去掉可能的日
                if m.isdigit():
                    return f"{parts[0]}-{int(m):02d}"
        return None

def normalize_value(field: str, v: object):
    if field == "year_month":
        return to_year_month(v)
    if field in DEC_FIELDS:
        return to_decimal(v)
    if field in BOOL_FIELDS:
        return to_bool(v)
    if field in STR_FIELDS:
        if v is None:
            return None
        s = str(v).strip()
        return None if s == "" or s.lower() in {"nan", "none", "null"} else s
    return None if v is None else str(v).strip()

# ============== 只导前 50 条 ==============
def import_data_50():
    df = pd.read_csv(CSV_PATH, usecols=USECOLS, dtype=str, low_memory=False)
    print(f"总共有 {len(df)} 条数据，准备导入前 50 条（重复将被静默跳过）")

    records = []
    for _, row in df.head(50).iterrows():
        data = {field: normalize_value(field, row[col]) for col, field in COLUMN_MAP.items()}
        records.append(FlightMarketRecord(**data))

    FlightMarketRecord.objects.bulk_create(records, batch_size=1000, ignore_conflicts=IGNORE_CONFLICTS)
    print("成功导入 50 条数据！")

# ============== 并行全量导入（进度） ==============
def _process_part(part_df: pd.DataFrame, batch_size: int,
                  progress_box: dict, lock: Lock, total_rows: int) -> int:
    close_old_connections()
    col_pos = {col: idx for idx, col in enumerate(part_df.columns)}
    to_create = []

    def bump(n_new: int):
        if n_new <= 0:
            return
        with lock:
            progress_box['inserted'] += n_new
            steps = progress_box['inserted'] // PROGRESS_STEP
            if steps > progress_box['last_steps']:
                progress_box['last_steps'] = steps
                n = progress_box['inserted']
                ratio = (n / total_rows) if total_rows else 1.0
                print(f"\r进度：{n}/{total_rows}（{ratio:.2%}）", end="", flush=True)

    for row in part_df.itertuples(index=False, name=None):
        data = {}
        for col, field in COLUMN_MAP.items():
            val = row[col_pos[col]]
            data[field] = normalize_value(field, val)
        to_create.append(FlightMarketRecord(**data))

        if len(to_create) >= batch_size:
            with transaction.atomic():
                FlightMarketRecord.objects.bulk_create(
                    to_create, batch_size=batch_size, ignore_conflicts=IGNORE_CONFLICTS
                )
            bump(len(to_create))
            to_create.clear()

    if to_create:
        with transaction.atomic():
            FlightMarketRecord.objects.bulk_create(
                to_create, batch_size=batch_size, ignore_conflicts=IGNORE_CONFLICTS
            )
        bump(len(to_create))

    return len(part_df)

def import_data_parallel(workers: int = WORKERS, batch_size: int = BATCH_SIZE):
    df = pd.read_csv(CSV_PATH, usecols=USECOLS, dtype=str, low_memory=False)

    # 可选：先按唯一键（CSV 列名）去重，减少数据库冲突（方案A+去重更稳）
    # raw_total = len(df)
    # df = df.drop_duplicates(subset=["Origin", "Destination", "Equipment", "YearMonth"], keep="last")
    # print(f"去重后剩 {len(df)} 条，移除了 {raw_total - len(df)} 条重复")

    total = len(df)
    print(f"总共有 {total} 条数据，开始并行导入（workers={workers}, batch_size={batch_size}，重复将被静默跳过）")

    parts = np.array_split(df, max(workers * 4, 1))
    lock = Lock()
    progress_box = {'inserted': 0, 'last_steps': 0}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_part, p, batch_size, progress_box, lock, total) for p in parts]
        for f in as_completed(futures):
            f.result()

    print()  # 换行
    print("全部导入完成！")

# ================= 入口 =================
if __name__ == "__main__":
    # 小样本
    # import_data_50()

    # 全量
    import_data_parallel()
