import json
import decimal
import pandas as pd
import io
from .models import (FlightMarketRecord)

COLUMN_MAPPING = {
    "route_total_flights": "route_total_flights",
    "route_total_seats": "route_total_seats",
    "Seats":"equipment_total_seats",
    "Frequency":"equipment_total_flights",
    "Time series": "year_month",
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

    # ===========================
    if df is not None and not df.empty:
        cols = list(df.columns)
        print(cols)

        # 1. 判断是否已经有 route_total_*（包含首字母大写版本）
        has_route_flights = ("route_total_flights" in cols) or ("Route_total_flights" in cols)
        has_route_seats = ("route_total_seats" in cols) or ("Route_total_seats" in cols)

        # 只在“完全没有这两列”的时候才自动算
        if not has_route_flights and not has_route_seats:
            # 2. 找 Frequency / Seats 或 equipment_total_* 作为数据源

            # 座位来源：优先 Seats，其次 equipment_total_seats / Equipment_total_seats
            seats_source_col = None
            if "Seats" in cols:
                seats_source_col = "Seats"
            elif "equipment_total_seats" in cols:
                seats_source_col = "equipment_total_seats"
            elif "Equipment_total_seats" in cols:
                seats_source_col = "Equipment_total_seats"

            # 班次来源：优先 Frequency，其次 equipment_total_flights / Equipment_total_flights
            flights_source_col = None
            if "Frequency" in cols:
                flights_source_col = "Frequency"
            elif "equipment_total_flights" in cols:
                flights_source_col = "equipment_total_flights"
            elif "Equipment_total_flights" in cols:
                flights_source_col = "Equipment_total_flights"

            # 如果两个源都完全没有，就不要算了，后面逻辑照旧
            if seats_source_col or flights_source_col:
                # 3. 找分组维度：年月 + 起点 + 终点 + 机型（同一航线同一日期不同机型）
                # year_month 有可能叫 Time series，你之前已经在 COLUMN_MAPPING 那边处理过，
                # 这里再兜一层。
                if "year_month" in cols:
                    ym_col = "year_month"
                elif "Time series" in cols:
                    ym_col = "Time series"
                else:
                    ym_col = None

                # origin / destination 可能有 *_code，这里都兼容一下
                if "Origin" in cols:
                    origin_col = "Origin"
                elif "origin_code" in cols:
                    origin_col = "origin_code"
                else:
                    origin_col = None

                if "Destination" in cols:
                    dest_col = "Destination"
                elif "destination_code" in cols:
                    dest_col = "destination_code"
                else:
                    dest_col = None

                equip_col = "equipment" if "equipment" in cols else None

                group_cols = [c for c in [ym_col, origin_col, dest_col] if c]
                # 只有当这些关键维度列存在时才做聚合
                if group_cols:
                    if flights_source_col:
                        # 同一 (年月+航线) 的 Frequency / equipment_total_flights 求和
                        df["route_total_flights"] = df.groupby(group_cols)[flights_source_col].transform("sum")
                        print(df["route_total_flights"])
                    if seats_source_col:
                        # 同一 (年月+航线) 的 Seats / equipment_total_seats 求和
                        df["route_total_seats"] = df.groupby(group_cols)[seats_source_col].transform("sum")
                        print(df["route_total_seats"])

    rows = []
    print(df)
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
        print(data)
        rows.append({
            "index": len(rows),
            "key": key,
            "has_conflict": existing is not None,
            "data": data,
            "old_data": old_data,  # 添加旧数据用于对比
        })

    return rows