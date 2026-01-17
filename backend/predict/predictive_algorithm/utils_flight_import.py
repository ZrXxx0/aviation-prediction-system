import json
import decimal
import pandas as pd
import numpy as np
import io
import os
import math
from django.db.models import Q
from predict.models import FlightMarketRecord

current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/...
base_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'Predict_Datas')  # backend/Predict_Datas
EQUIP_MAP_PATH = os.path.join(base_dir, 'equipment_fleet_map.xlsx')
SEAT_MAP_PATH = os.path.join(base_dir, 'predict_fleetparam.xls')

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


def process_simple_csv_logic(df_flight):
    """
    处理只有几列的精简版 CSV，融合辅助文件，计算所需的字段。
    返回处理后的 DataFrame，列名已对齐 FlightMarketRecord 的字段。
    """
    # 检查辅助文件是否存在
    if not os.path.exists(EQUIP_MAP_PATH) or not os.path.exists(SEAT_MAP_PATH):
        raise FileNotFoundError("服务器缺少辅助计算文件 (equipment_fleet_map 或 predict_fleetparam)，无法处理精简模式。")

    # 读取辅助文件
    df_equip_map = pd.read_excel(EQUIP_MAP_PATH, dtype={'equipment': str})
    df_seat_map = pd.read_excel(SEAT_MAP_PATH)

    # 1. 清洗键值
    if 'Specific Aircraft Code' in df_flight.columns:
        df_flight['Specific Aircraft Code'] = df_flight['Specific Aircraft Code'].astype(str).str.strip()
    df_equip_map['equipment'] = df_equip_map['equipment'].astype(str).str.strip()
    df_equip_map['fleet_type'] = df_equip_map['fleet_type'].astype(str).str.strip()
    df_seat_map['fleet_type'] = df_seat_map['fleet_type'].astype(str).str.strip()

    # 2. 第一次关联：匹配机型 (Left Join)
    merged = pd.merge(
        df_flight,
        df_equip_map,
        left_on='Specific Aircraft Code',
        right_on='equipment',
        how='left'
    )

    # 3. 第二次关联：匹配座位参数
    merged = pd.merge(merged, df_seat_map, on='fleet_type', how='left')

    # 4. 计算逻辑
    merged['avg_seats'] = merged['avg_seats'].fillna(100).replace(0, 100)

    # 计算机型总班次 (总座位/平均座位)，并向上取整
    merged['calc_flights'] = merged['Seats (Total)'] / merged['avg_seats']
    merged['calc_flights'] = np.ceil(merged['calc_flights'])

    # 5. 构造标准 DataFrame
    final_df = pd.DataFrame()
    # 映射到数据库字段名
    final_df['year_month'] = merged['Time series']
    final_df['origin'] = merged['Dep Airport Code']
    final_df['destination'] = merged['Arr Airport Code']
    final_df['equipment'] = merged['Specific Aircraft Code']  # 确保 equipment 存在
    final_df['distance_km'] = merged['GCD (km)']
    final_df['equipment_total_flights'] = merged['calc_flights']
    final_df['equipment_total_seats'] = merged['Seats (Total)']

    # 6. 聚合计算 Route 级别的数据 (Route Total Flights/Seats)
    # 按照 年月+起点+终点 分组，计算同航线所有机型的总和，赋值回每一行
    g = final_df.groupby(['year_month', 'origin', 'destination'])
    final_df['route_total_flights'] = g['equipment_total_flights'].transform('sum')
    final_df['route_total_seats'] = g['equipment_total_seats'].transform('sum')

    return final_df


def fetch_existing_records_in_batch(keys_list):
    """
    批量查询数据库。
    keys_list: [(ym, origin, dest, equipment), ...]  <-- 修改：增加了 equipment
    """
    if not keys_list:
        return {}

    chunk_size = 1000
    found_records_map = {}

    total_keys = len(keys_list)
    for i in range(0, total_keys, chunk_size):
        chunk = keys_list[i:i + chunk_size]
        query = Q()
        for ym, origin, dest, equip in chunk:
            # 修改：查询条件加入 equipment
            query |= Q(year_month=ym, origin=origin, destination=dest, equipment=equip)

        records = FlightMarketRecord.objects.filter(query)

        for r in records:
            # 修改：Key 加入 equipment
            k = f"{r.year_month}-{r.origin}-{r.destination}-{r.equipment}"
            found_records_map[k] = r

    return found_records_map


def parse_csv_content(csv_content=None, file_obj=None):
    """
    解析流程入口
    """
    try:
        if file_obj:
            file_obj.seek(0)
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

    if df is not None and not df.empty:
        df.columns = df.columns.str.strip()
        cols = list(df.columns)

        # === 核心判断：是精简版还是完整版？===
        # 判断依据：是否有 "Specific Aircraft Code" 这个特征列
        is_simple_mode = 'Specific Aircraft Code' in cols and 'Dep Airport Code' in cols

        if is_simple_mode:
            # 走精简版逻辑，处理完后得到标准的 df
            df = process_simple_csv_logic(df)
            # 处理后的 df 列名已经是标准的 'year_month', 'origin' 等
            # 为了适配下面的循环，我们不需要再做 COLUMN_MAPPING 的重命名，
            # 但下面的循环依赖 COLUMN_MAPPING 来提取数据，所以我们需要伪造一下
            # 或者，更简单的方法：直接重构下面的提取逻辑。
            # 为了代码复用，我们将 df 的列名视为最终字段名。
        else:
            # === 原有的完整版逻辑 (计算 route_total 等) ===
            # ... (这里保留你原本的计算 route_total_flights 的逻辑) ...
            # 为了节省篇幅，这里假设还是你原来的逻辑，只是列名清洗一下
            pass

    rows = []
    keys_to_fetch = []

    for i, row in df.iterrows():
        data = {}

        if is_simple_mode:
            # 精简模式下，df 的列名已经是数据库字段名了
            # 我们直接把非空的字段拿出来
            valid_fields = set(COLUMN_MAPPING.values())
            for col in df.columns:
                if col in valid_fields:
                    val = row[col]
                    data[col] = _normalize_for_json(val)
        else:
            # 完整模式：走映射
            for col_name, field_name in COLUMN_MAPPING.items():
                if col_name in df.columns:
                    value = row[col_name]
                    if field_name == "international_flight":
                        if value is not None:
                            value = _bool_from_01(value)
                    data[field_name] = _normalize_for_json(value)

        # 补全 None
        all_target_fields = set(COLUMN_MAPPING.values())
        for f_name in all_target_fields:
            if f_name not in data:
                data[f_name] = None

        # === 关键修复：Key 的生成 ===
        raw_ym = data.get("year_month")
        raw_origin = data.get("origin")
        raw_dest = data.get("destination")
        raw_equip = data.get("equipment")  # 获取机型

        ym = str(raw_ym).strip() if raw_ym is not None else ""
        origin = str(raw_origin).strip().upper() if raw_origin is not None else ""
        dest = str(raw_dest).strip().upper() if raw_dest is not None else ""
        equipment = str(raw_equip).strip() if raw_equip is not None else ""  # 机型也是 Key 的一部分

        # 如果没有机型，这行数据可能有问题，但在旧数据兼容上可能要注意
        if not ym or not origin or not dest or not equipment:
            continue

        # 修改：Key 包含 equipment
        key_str = f"{ym}-{origin}-{dest}-{equipment}"

        # 修改：查询列表包含 equipment
        keys_to_fetch.append((ym, origin, dest, equipment))

        rows.append({
            "index": len(rows),
            "key": key_str,
            "data": data,
        })

    # 批量查询
    existing_map = fetch_existing_records_in_batch(keys_to_fetch)

    result_rows = []
    for item in rows:
        key = item["key"]
        data = item["data"]
        existing = existing_map.get(key)

        has_conflict = False
        old_data = None

        if existing:
            old_data = {}
            excluded_fields = {'id', 'created_at', 'updated_at'}
            for field in FlightMarketRecord._meta.get_fields():
                if field.many_to_many or field.one_to_many or field.many_to_one: continue
                if field.name in excluded_fields: continue
                if hasattr(existing, field.name):
                    val = getattr(existing, field.name)
                    if isinstance(val, decimal.Decimal):
                        old_data[field.name] = float(val)
                    elif hasattr(val, 'isoformat'):
                        old_data[field.name] = val.isoformat()
                    else:
                        old_data[field.name] = val

            # 冲突检测
            for field_key, new_value in data.items():
                if new_value is None: continue
                old_val_raw = getattr(existing, field_key, None)
                if _values_are_different(old_val_raw, new_value):
                    has_conflict = True
                    break

        result_rows.append({
            "index": item["index"],
            "key": key,
            "has_conflict": has_conflict,
            "data": data,
            "old_data": old_data,
        })

    return result_rows