import json
import decimal
import pandas as pd
import io
from .models import (FlightMarketRecord)

COLUMN_MAPPING = {
    "YearMonth": "year_month",
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

def _bool_from_01(v):
    if v in (1, "1", "Y", "y", "true", "True"):
        return True
    return False

def _normalize_for_json(v):
    if v is None:
        return None
    return v  # 直接返回，前端能接受 string/number/bool

def parse_upload_file_for_preview(file_obj):
    """
    解析文件，返回 list[dict]，每个 dict 描述一行数据及是否冲突：
    [
      {
        "index": 0,
        "key": "2024-01-PEK-SHA",
        "has_conflict": true/false,
        "data": { "year_month": "...", "origin": "...", ... }
      }, ...
    ]
    """
    name = file_obj.name.lower()
    if name.endswith(".xls") or name.endswith(".xlsx"):
        df = pd.read_excel(file_obj)
    else:
        df = pd.read_csv(file_obj)

    rows = []

    for i, row in df.iterrows():
        data = {}
        for col_name, field_name in COLUMN_MAPPING.items():
            if col_name not in df.columns:
                continue
            value = row[col_name]

            if field_name == "international_flight":
                value = _bool_from_01(value)
            if pd.isna(value):
                value = None

            data[field_name] = _normalize_for_json(value)

        ym = (data.get("year_month") or "").strip()
        origin = (data.get("origin") or "").strip()
        dest = (data.get("destination") or "").strip()
        if not ym or not origin or not dest:
            continue

        key = f"{ym}-{origin}-{dest}"

        existing = FlightMarketRecord.objects.filter(
            year_month=ym,
            origin=origin,
            destination=dest,
        ).first()

        rows.append({
            "index": len(rows),
            "key": key,
            "has_conflict": existing is not None,
            "data": data,
        })

    return rows

def parse_csv_content(csv_content):
    """
    解析 CSV 文本内容，返回 list[dict]，每个 dict 描述一行数据及是否冲突：
    [
      {
        "index": 0,
        "key": "2024-01-PEK-SHA",
        "has_conflict": true/false,
        "data": { "year_month": "...", "origin": "...", ... }
      }, ...
    ]
    """
    try:
        # 将字符串转换为文件对象
        csv_file = io.StringIO(csv_content)
        df = pd.read_csv(csv_file)
    except Exception as e:
        raise ValueError(f"CSV 解析失败: {str(e)}")

    rows = []

    for i, row in df.iterrows():
        data = {}
        for col_name, field_name in COLUMN_MAPPING.items():
            if col_name not in df.columns:
                continue
            value = row[col_name]

            if field_name == "international_flight":
                value = _bool_from_01(value)
            if pd.isna(value):
                value = None

            data[field_name] = _normalize_for_json(value)

        ym = (data.get("year_month") or "").strip()
        origin = (data.get("origin") or "").strip().upper()
        dest = (data.get("destination") or "").strip().upper()
        if not ym or not origin or not dest:
            continue

        key = f"{ym}-{origin}-{dest}"

        existing = FlightMarketRecord.objects.filter(
            year_month=ym,
            origin=origin,
            destination=dest,
        ).first()

        # 构建旧数据字典（如果存在）
        old_data = None
        if existing:
            old_data = {}
            # 系统管理的字段，不参与比较
            excluded_fields = {'id', 'created_at', 'updated_at'}
            # 只获取实际的模型字段，排除关系字段和系统管理字段
            for field in FlightMarketRecord._meta.get_fields():
                # 跳过关系字段（ForeignKey, ManyToManyField, OneToOneField）
                if field.many_to_many or field.one_to_many or field.many_to_one:
                    continue
                # 跳过系统管理的字段（id, created_at, updated_at）
                if field.name in excluded_fields:
                    continue
                if hasattr(existing, field.name):
                    try:
                        value = getattr(existing, field.name)
                        if value is not None:
                            # 处理 Decimal 类型
                            if isinstance(value, decimal.Decimal):
                                old_data[field.name] = float(value)
                            # 处理日期时间类型
                            elif hasattr(value, 'isoformat'):
                                old_data[field.name] = value.isoformat()
                            else:
                                old_data[field.name] = value
                        else:
                            old_data[field.name] = None
                    except Exception:
                        # 跳过无法访问的字段
                        continue

        rows.append({
            "index": len(rows),
            "key": key,
            "has_conflict": existing is not None,
            "data": data,
            "old_data": old_data,  # 添加旧数据用于对比
        })

    return rows