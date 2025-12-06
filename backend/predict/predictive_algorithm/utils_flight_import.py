import json
import decimal
import pandas as pd
import io
import math
from django.db.models import Q
from predict.models import (FlightMarketRecord)

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
    # 1. 处理 Pandas 的空值 (NaN, None, NaT)
    if pd.isna(v) or v is None:
        return None

    # 2. 处理 NumPy 数据类型 (int64, float64 等)
    # .item() 方法可以将 numpy 标量转换为原生的 Python int/float
    if hasattr(v, 'item'):
        return v.item()

    # 3. 如果是其他对象（如直接传来的 int/str），直接返回
    return v


def _values_are_different(db_val, upload_val):
    """
    辅助函数：比较数据库值和上传值是否不同。
    处理 float vs Decimal, String strip 等问题。
    返回 True 表示有冲突（值不同），False 表示无冲突。
    """
    # 1. 如果上传的是 None，根据需求，不视为冲突（忽略该列）
    if upload_val is None:
        return False

    # 2. 如果数据库是 None，而上传了值 (非None)，肯定是冲突（或者叫新数据覆盖）
    if db_val is None:
        return True

    # 3. 类型转换比对
    try:
        # 处理数字类型的比对 (Decimal vs Float/Int)
        if isinstance(db_val, (decimal.Decimal, float, int)) and isinstance(upload_val, (decimal.Decimal, float, int)):
            # 统一转成 float 进行比对，允许微小误差
            return not math.isclose(float(db_val), float(upload_val), rel_tol=1e-9)

        # 处理布尔值
        if isinstance(db_val, bool) or isinstance(upload_val, bool):
            return db_val != upload_val

        # 处理字符串 (去除空格后比对)
        str_db = str(db_val).strip()
        str_up = str(upload_val).strip()
        return str_db != str_up

    except Exception:
        # 如果类型太复杂无法比对，直接按默认不相等处理
        return db_val != upload_val

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

        # Iterate through the mapping
        for col_name, field_name in COLUMN_MAPPING.items():
            # CRITICAL FIX: Only process if the column actually exists in the DataFrame
            if col_name in df.columns:
                value = row[col_name]

                if field_name == "international_flight":
                    if value is not None:
                        value = _bool_from_01(value)

                if pd.isna(value):
                    value = None

                # Only write to data if we found a value.
                # This prevents a missing alias (like "YearMonth") from overwriting
                # a found alias (like "Time series") with None.
                data[field_name] = _normalize_for_json(value)

        # OPTIONAL: Fill remaining fields with None if they were never found
        all_target_fields = set(COLUMN_MAPPING.values())
        for f_name in all_target_fields:
            if f_name not in data:
                data[f_name] = None

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


def fetch_existing_records_in_batch(keys_list):
    """
    批量查询数据库。
    keys_list: [(ym, origin, dest), ...]
    返回: dict { "ym-origin-dest": record_obj }
    """
    if not keys_list:
        return {}

    # 为了避免 SQL 语句过长报错，建议分块查询，比如每次查 1000 条
    chunk_size = 1000
    found_records_map = {}

    total_keys = len(keys_list)
    for i in range(0, total_keys, chunk_size):
        chunk = keys_list[i:i + chunk_size]

        # 构建 Q 查询对象: (A and B and C) OR (D and E and F) ...
        query = Q()
        for ym, origin, dest in chunk:
            query |= Q(year_month=ym, origin=origin, destination=dest)

        # 执行查询
        records = FlightMarketRecord.objects.filter(query)

        # 将结果存入字典，Key 必须和后续生成的 key 保持一致
        for r in records:
            # 确保 key 的格式与下面处理逻辑一致
            k = f"{r.year_month}-{r.origin}-{r.destination}"
            found_records_map[k] = r

    return found_records_map

def parse_csv_content(csv_content=None, file_obj=None):
    """
    解析表格内容（CSV 文本或上传文件），返回 list[dict]，每个 dict 描述一行数据及是否冲突：
    [
      {
        "index": 0,
        "key": "2024-01-PEK-SHA",
        "has_conflict": true/false,
        "data": { "year_month": "...", "origin": "...", ... }
      }, ...
    ]
    """
    # 优先使用上传的文件，其次使用 CSV 文本
    try:
        if file_obj:
            # 确保文件指针在开头
            try:
                file_obj.seek(0)
            except Exception:
                pass

            name = file_obj.name.lower()
            if name.endswith(".xls") or name.endswith(".xlsx"):
                df = pd.read_excel(file_obj)
            else:
                df = pd.read_csv(file_obj)
        else:
            if csv_content is None:
                raise ValueError("缺少表格内容")
            csv_file = io.StringIO(csv_content)
            df = pd.read_csv(csv_file)
    except Exception as e:
        raise ValueError(f"文件解析失败: {str(e)}")

    # ===========================
    if df is not None and not df.empty:
        df.columns = df.columns.str.strip()
        cols = list(df.columns)
        # print(cols)

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
                        df["route_total_flights"] = df["route_total_flights"].fillna(0)
                        # print(df["route_total_flights"])
                    if seats_source_col:
                        # 同一 (年月+航线) 的 Seats / equipment_total_seats 求和
                        df["route_total_seats"] = df.groupby(group_cols)[seats_source_col].transform("sum")
                        df["route_total_seats"] = df["route_total_seats"].fillna(0)
                        # print(df["route_total_seats"])

    rows = []
    # print(df.columns)
    pending_items = []

    # 需要查询的 key 列表
    keys_to_fetch = []

    # --- 2. 第一遍循环：解析数据，准备 Key ---
    for i, row in df.iterrows():
        data = {}

        # Iterate through the mapping
        for col_name, field_name in COLUMN_MAPPING.items():
            # CRITICAL FIX: Only process if the column actually exists in the DataFrame
            if col_name in df.columns:
                value = row[col_name]

                if field_name == "international_flight":
                    if value is not None:
                        value = _bool_from_01(value)

                if pd.isna(value):
                    value = None

                # Only write to data if we found a value.
                # This prevents a missing alias (like "YearMonth") from overwriting
                # a found alias (like "Time series") with None.
                data[field_name] = _normalize_for_json(value)

        # OPTIONAL: Fill remaining fields with None if they were never found
        all_target_fields = set(COLUMN_MAPPING.values())
        for f_name in all_target_fields:
            if f_name not in data:
                data[f_name] = None

        # 1. 获取原始值
        # print(data)
        raw_ym = data.get("year_month")
        raw_origin = data.get("origin")
        raw_dest = data.get("destination")

        # 2. 安全转换为字符串并去除空格
        # 说明: 如果是 None，转为空字符串；如果是数字/日期对象，先 str() 转为字符串再 strip()
        ym = str(raw_ym).strip() if raw_ym is not None else ""
        origin = str(raw_origin).strip().upper() if raw_origin is not None else ""
        dest = str(raw_dest).strip().upper() if raw_dest is not None else ""

        if not ym or not origin or not dest:
            continue

        key_str = f"{ym}-{origin}-{dest}"

        # 存入待查列表
        keys_to_fetch.append((ym, origin, dest))

        pending_items.append({
            "index": len(pending_items),  # 临时索引
            "key": key_str,
            "data": data,
        })

    # --- 3. 批量查询数据库 (关键优化) ---
    # 传入 list[(ym, org, dst)]，返回 dict { "ym-org-dst": obj }
    existing_map = fetch_existing_records_in_batch(keys_to_fetch)

    # --- 4. 第二遍循环：内存比对 ---
    for item in pending_items:
        key = item["key"]
        data = item["data"]

        # 直接从字典获取，不再查库
        existing = existing_map.get(key)

        has_conflict = False
        old_data = None

        if existing:
            old_data = {}
            # 序列化旧数据 (用于前端展示)
            excluded_fields = {'id', 'created_at', 'updated_at'}
            # 这里也可以优化：如果字段非常多，这一步也会耗时，
            # 但通常是在内存操作，比 DB 快得多。
            for field in FlightMarketRecord._meta.get_fields():
                if field.many_to_many or field.one_to_many or field.many_to_one:
                    continue
                if field.name in excluded_fields:
                    continue
                if hasattr(existing, field.name):
                    val = getattr(existing, field.name)
                    if isinstance(val, decimal.Decimal):
                        old_data[field.name] = float(val)
                    elif hasattr(val, 'isoformat'):
                        old_data[field.name] = val.isoformat()
                    else:
                        old_data[field.name] = val

            # === 冲突检测 ===
            for field_key, new_value in data.items():
                if new_value is None:
                    continue  # 没上传的列，跳过

                old_val_raw = getattr(existing, field_key, None)

                if _values_are_different(old_val_raw, new_value):
                    has_conflict = True
                    break

        rows.append({
            "index": item["index"],
            "key": key,
            "has_conflict": has_conflict,
            "data": data,
            "old_data": old_data,
        })

    return rows