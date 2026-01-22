from django.conf import settings
from collections import OrderedDict
import datetime
import csv
from django.db.models import Q
import django
import sys

from collections import defaultdict
import os
import pandas as pd
from django.conf import settings
from django.db.models import Max

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()
from predict.models import FlightMarketRecord,FleetParam
# 配置路径
ROUTE_RANKING_CSV = os.path.join(
    settings.BASE_DIR, "Predict_Datas", "route_ranking2.csv"
)
ROUTE_RANKING_CSV2 = os.path.join(
    settings.BASE_DIR, "Predict_Datas", "route_panel_ranking.csv"
)


# 映射表 Excel 的路径
EQUIPMENT_FLEET_XLSX = os.path.join(
    settings.BASE_DIR, "Predict_Datas", "equipment_fleet_map.xlsx"
)

# 全局缓存
_equipment_fleet_map_cache = None


def get_equipment_fleet_map():
    """
    从 Excel 文件中读取映射：
    {
        "equipment编号": "机型类别字符串",
        ...
    }
    只读一次，后面都用内存缓存。
    Excel 至少需要两列：equipment, fleet_type（列名按实际情况改）
    """
    global _equipment_fleet_map_cache
    if _equipment_fleet_map_cache is not None:
        return _equipment_fleet_map_cache

    if not os.path.exists(EQUIPMENT_FLEET_XLSX):
        # 文件不存在，可以选择抛异常或者返回空 dict
        # 这里先返回空 dict，方便接口不直接炸掉
        print(f"[get_equipment_fleet_map] 映射文件不存在: {EQUIPMENT_FLEET_XLSX}")
        _equipment_fleet_map_cache = {}
        return _equipment_fleet_map_cache

    # 读取 Excel
    try:
        df = pd.read_excel(EQUIPMENT_FLEET_XLSX)  # 默认读第一个 sheet
    except Exception as e:
        print(f"[get_equipment_fleet_map] 读取 Excel 失败: {e}")
        _equipment_fleet_map_cache = {}
        return _equipment_fleet_map_cache

    # 假设 Excel 里有两列：equipment, fleet_type
    # 如果你的列名是中文，比如“机型编号”“机型类别”，把这里改成对应的列名即可
    equipment_col = "equipment"
    fleet_type_col = "fleet_type"

    if equipment_col not in df.columns or fleet_type_col not in df.columns:
        print(f"[get_equipment_fleet_map] Excel 中缺少列 {equipment_col} 或 {fleet_type_col}")
        _equipment_fleet_map_cache = {}
        return _equipment_fleet_map_cache

    mapping = {}

    for _, row in df.iterrows():
        equipment = str(row[equipment_col]).strip() if not pd.isna(row[equipment_col]) else ""
        fleet_type = str(row[fleet_type_col]).strip() if not pd.isna(row[fleet_type_col]) else ""

        if not equipment or not fleet_type:
            continue

        mapping[equipment] = fleet_type

    _equipment_fleet_map_cache = mapping
    print(f"[get_equipment_fleet_map] 已从 Excel 加载 {len(mapping)} 条 equipment 映射")
    return _equipment_fleet_map_cache

def get_routes_from_csv(limit: int = None):
    """
    从 route_ranking.csv 里按行号取前 `limit` 条航线，若未指定 limit，则返回所有航线。

    参数:
      - limit: 要获取的航线数量。如果为 None，则获取所有航线。

    返回:
      - list: 包含航线的元组列表，每个元组包含 (origin, destination)。
    """
    routes = []

    # 检查文件是否存在
    if not os.path.exists(ROUTE_RANKING_CSV2):
        print(f"CSV file does not exist: {ROUTE_RANKING_CSV2}")
        return routes

    # 打开并读取 CSV 文件
    with open(ROUTE_RANKING_CSV2, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        # 根据 limit 参数限制返回的航线数量
        for idx, row in enumerate(reader, start=1):
            origin = row.get("Origin")
            dest = row.get("Destination")

            # 跳过字段缺失的行
            if not origin or not dest:
                continue

            # 如果设置了 limit，则获取前 limit 条航线
            if limit is not None and idx > limit:
                break

            # 将航线添加到结果列表
            routes.append((origin, dest))

    print(f"Total routes fetched: {len(routes)}")
    return routes


def classify_fleet(records_for_fleet):
    """
    按 equipment -> EquipmentFleetMap.fleet_type 来分类，
    然后统计每个机型类别的座位总数。
    """
    fleet_stats = defaultdict(int)

    # 一次拿到 equipment -> fleet_type 的映射
    equipment_map = get_equipment_fleet_map()

    for record in records_for_fleet:
        flights = float(record.equipment_total_flights or 0)
        seats = float(record.equipment_total_seats or 0)

        # 你之前这里就用过这个判断，可以保留：无有效航班/座位就跳过
        if flights <= 0 or seats <= 0:
            continue

        # 读取 equipment 编号
        equipment = (getattr(record, "equipment", "") or "").strip()
        if not equipment:
            # 没有 equipment 信息，直接跳过（也可以按需要记录 log）
            continue

        # 用新表来查所属机型类别
        fleet_type = equipment_map.get(equipment)

        if not fleet_type:
            # 映射表里没有这个 equipment，可以选择：
            # 1) 归到某个“其他”类别：
            #    fleet_type = "其他机型"
            # 2) 或者干脆丢弃这部分：
            #    continue
            # 这里先选择丢弃，避免污染比例
            continue

        # 保留你原来的统计逻辑：不同类别累加 seats
        fleet_stats[fleet_type] += seats

    return fleet_stats




def save_fleet_proportions_to_csv(fleet_proportions, filename="fleet_proportions.csv"):
    """将机队比例保存到项目根目录下 Predict_Datas 目录"""
    import os
    import csv

    # 存到 backend/Predict_Datas 下
    save_dir = os.path.join(settings.BASE_DIR, "Predict_Datas")
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, filename)

    header = [
        "origin", "destination",
        "支线客机",
        "小型窄体客机",
        "中型窄体客机",
        "大型窄体客机",
        "小型宽体客机",
        "中型宽体客机",
        "大型宽体客机",
    ]

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for (origin, destination), proportions in fleet_proportions.items():
            row = [origin, destination]
            for fleet_name in fleet_mapping.keys():
                row.append(proportions.get(fleet_name, 0))
            writer.writerow(row)

    print("已写入:", file_path)

def get_fleet_mapping():
    """
    从 FleetParam 表中按座位数递增获取映射：
    {
        "支线客机": 76,
        "小型窄体客机": 117,
        ...
    }
    """
    mapping = OrderedDict()

    # 只要有 avg_seats 的机型，按 avg_seats 排序
    qs = FleetParam.objects.exclude(avg_seats__isnull=True).order_by("avg_seats")

    for fp in qs:
        # 如果 avg_seats 是 Decimal，这里转成 float / int 都可以
        mapping[fp.fleet_type] = float(fp.avg_seats)

    return mapping



def get_market_data_bulk(routes, year_months, batch_size=500):
    """
    批量从数据库读取市场数据（按你提供的 routes 作为航线对代表）：
    - routes: [(origin, destination), ...]，你已经保证每对双向航线只保留了一条
    - 查询时：对每个 (o, d) 查询 o->d 和 d->o
    - 返回: data_map[(origin, destination)] = [双向所有 FlightMarketRecord, ...]
    """
    data_map = defaultdict(list)

    # 建一个 无向 -> 代表 key 的映射，方便把查询结果按你的 routes key 存
    undirected_to_canonical = {}
    for o, d in routes:
        undirected_key = tuple(sorted((o, d)))
        undirected_to_canonical[undirected_key] = (o, d)

    # 分批处理，避免 Q 过长
    for i in range(0, len(routes), batch_size):
        batch_routes = routes[i: i + batch_size]

        q_objects = Q()
        batch_undirected_keys = set()

        for origin, dest in batch_routes:
            # 对这一对，查询正反两个方向
            q_objects |= (Q(origin=origin, destination=dest) |
                          Q(origin=dest, destination=origin))

            # 记录这一批里涉及到的无向 key
            batch_undirected_keys.add(tuple(sorted((origin, dest))))

        if not q_objects.children:
            continue

        records = FlightMarketRecord.objects.filter(
            q_objects,
            year_month__in=year_months
        )

        for record in records:
            undirected_key = tuple(sorted((record.origin, record.destination)))

            # 找到这一对对应的“代表 key”（也就是你 routes 里那条）
            canonical_key = undirected_to_canonical.get(undirected_key)
            if canonical_key is None:
                # 理论上不会发生，除非库里有你 routes 没有的 pair
                continue

            data_map[canonical_key].append(record)

    return data_map



def double_filter_routes(report_path=None, top_n=None,
                         valid_csv_path=None, other_csv_path=None):
    """
    无向 Top-N 航线筛选：
    - 将 A->B 和 B->A 视为同一条航线对；
    - 将其 Calculated_Value 相加后排序；
    - 只保留一条航线名，按字母顺序 (min(Origin, Destination), max(Origin, Destination))；
    - 返回 / 写出的是“每个无向航线对一行”的结果。

    参数:
        report_path: 航线报告文件路径
        top_n: 前 n 个无向航线对
        valid_csv_path: 筛选出的 Top-N 航线对保存路径（可选）
        other_csv_path: 其余航线对保存路径（可选）

    返回:
        (final_routes, remaining_routes)
        final_routes: Top-N 无向航线对 DataFrame
        remaining_routes: 剩余无向航线对 DataFrame
    """
    # 1. 读取航线报告
    if report_path is None:
        print("错误: 必须提供 report_path")
        return pd.DataFrame(), pd.DataFrame()

    route_report = pd.read_csv(report_path)

    # 2. 确保必要的列存在
    required_cols = ['Origin', 'Destination', 'Calculated_Value']
    for col in required_cols:
        if col not in route_report.columns:
            print(f"错误: 报告中缺少列 {col}")
            return pd.DataFrame(), pd.DataFrame()

    # 3. 确定排序依据列
    sort_col = 'Calculated_Value'
    if sort_col not in route_report.columns and 'Total_Seats_Prev_Year' in route_report.columns:
        sort_col = 'Total_Seats_Prev_Year'

    # 4. Top-N 参数
    if top_n is None:
        print("未提供 top_n 参数，将对所有无向航线对排序并全部保留")
    else:
        print(f"筛选模式: 无向 Top-N (依据 {sort_col} 聚合 A<->B 总和，每对仅保留一条航线名，Top {top_n})")

    print(f"筛选模式: 无向 Top-N (依据 {sort_col} 聚合 A<->B 总和，每对仅保留一条航线名)")

    # 4.1 创建无向标识符：按字母顺序排序
    # 例如 SZX-PEK 和 PEK-SZX 都会变成 ('PEK', 'SZX')
    route_report['Undirected_Pair_ID'] = route_report.apply(
        lambda row: tuple(sorted([str(row['Origin']), str(row['Destination'])])),
        axis=1
    )

    # 4.2 按无向标识符聚合
    #   - 聚合 sort_col 求和 (Pair_Total_Value)
    #   - 如果有 Min_YearMonth / Max_YearMonth，则取最小/最大，方便生成 Time_Span
    agg_dict = {sort_col: 'sum'}
    if 'Min_YearMonth' in route_report.columns:
        agg_dict['Min_YearMonth'] = 'min'
    if 'Max_YearMonth' in route_report.columns:
        agg_dict['Max_YearMonth'] = 'max'

    pair_stats = route_report.groupby('Undirected_Pair_ID').agg(agg_dict).reset_index()
    pair_stats.rename(columns={sort_col: 'Pair_Total_Value'}, inplace=True)

    # 4.3 把无向 ID 拆回 Origin / Destination（已经是按字母顺序排好的）
    pair_stats['Origin'] = pair_stats['Undirected_Pair_ID'].apply(lambda t: t[0])
    pair_stats['Destination'] = pair_stats['Undirected_Pair_ID'].apply(lambda t: t[1])

    # 4.4 按总价值降序排序
    pair_stats = pair_stats.sort_values(
        by='Pair_Total_Value',
        ascending=False
    ).reset_index(drop=True)


    # 4.5 根据 top_n 决定是否截断
    if top_n is None:
        # 不截断，全部当作“最终结果”，只做排序
        final_routes = pair_stats.copy()
        remaining_routes = pair_stats.iloc[0:0].copy()  # 空表，占位
    else:
        final_routes = pair_stats.head(top_n).copy()
        remaining_routes = pair_stats.iloc[top_n:].copy()

    print(f"最终筛选出 {len(final_routes)} 条无向航线对 (Top-N)")
    print(f"剩余 {len(remaining_routes)} 条无向航线对归入 Other")

    # 5. 添加 Time_Span（如果有年月信息）
    if 'Min_YearMonth' in final_routes.columns and 'Max_YearMonth' in final_routes.columns:
        try:
            final_routes['Min_YearMonth'] = pd.to_datetime(
                final_routes['Min_YearMonth']
            ).dt.strftime('%Y-%m')
            final_routes['Max_YearMonth'] = pd.to_datetime(
                final_routes['Max_YearMonth']
            ).dt.strftime('%Y-%m')
            final_routes['Time_Span'] = (
                final_routes['Min_YearMonth'].astype(str)
                + " to "
                + final_routes['Max_YearMonth'].astype(str)
            )
        except Exception as e:
            print(f"时间格式转换警告: {e}")

    # 6. 清理临时列
    final_routes.drop(columns=['Undirected_Pair_ID'], inplace=True, errors='ignore')
    remaining_routes.drop(columns=['Undirected_Pair_ID'], inplace=True, errors='ignore')

    # 7. 写 CSV（如果给了路径）
    if valid_csv_path is not None:
        final_routes.to_csv(valid_csv_path, index=False, encoding="utf-8-sig")
        print(f"已保存筛选结果到: {valid_csv_path}")

    if other_csv_path is not None:
        remaining_routes.to_csv(other_csv_path, index=False, encoding="utf-8-sig")
        print(f"已保存剩余航线到: {other_csv_path}")

    return final_routes.reset_index(drop=True), remaining_routes.reset_index(drop=True)



def get_miu_main(n: int = 500):
    csv_dir = os.path.dirname(ROUTE_RANKING_CSV)

    final_routes, remaining_routes = double_filter_routes(
        report_path=ROUTE_RANKING_CSV,
        valid_csv_path=os.path.join(csv_dir, "route_panel_ranking.csv"),
    )
    global fleet_mapping
    fleet_mapping = get_fleet_mapping()

    print("正在读取航线...")
    routes = get_routes_from_csv()  # 已经是“每对只保留一条”的 routes
    if not routes:
        print("未找到航线，退出。")
        return

    # 从数据库取最新 year_month（格式 YYYY-MM，字符串 max 就等价于时间最新）
    latest_ym = FlightMarketRecord.objects.aggregate(m=Max("year_month"))["m"]
    if not latest_ym:
        print("FlightMarketRecord 没有数据，退出。")
    latest_year = int(str(latest_ym)[:4])
    year_months = [f"{latest_year}-{m:02d}" for m in range(1, 13)]
    print(
        f"数据库最新 year_month={latest_ym} -> 使用最新年份={latest_year}，查询 {year_months[0]} ... {year_months[-1]}")

    print(f"正在批量获取数据库数据 (Routes: {len(routes)})...")
    records_map = get_market_data_bulk(routes, year_months)
    # print(records_map)
    print("数据库查询完成，开始计算比例...")

    fleet_proportions = {}

    # 全局统计（ALL -> ALL）
    global_fleet_stats = defaultdict(int)

    # ===== 追加：Other-Other（排除前500条后，按航线等权平均）=====
    EXCLUDE_TOP_N = n
    other_sum_props = defaultdict(float)
    other_route_cnt = 0
    other_fleet_keys = set()
    # ===========================================================

    total_count = len(routes)

    for idx, (origin, destination) in enumerate(routes, 1):
        if idx % 100 == 0:
            print(f"Processing {idx}/{total_count}...")

        # 直接用这条 route 作为 key，
        # 对应的 records 已经是 o->d + d->o 的合集
        records_for_fleet = records_map.get((origin, destination), [])

        if not records_for_fleet:
            continue

        # 现有逻辑：统计机型分布
        current_stats = classify_fleet(records_for_fleet)

        total_f = sum(current_stats.values())
        if total_f > 0:
            # μ 比例：直接定义在 (origin, destination) 这条“代表航线”上
            props = {k: v / total_f for k, v in current_stats.items()}
            fleet_proportions[(origin, destination)] = props

            # ===== 追加：收集 Other-Other 的均值统计（不影响你原有 ALL-ALL）=====
            if idx > EXCLUDE_TOP_N:
                other_route_cnt += 1
                other_fleet_keys.update(props.keys())
                for k, v in props.items():
                    other_sum_props[k] += v
            # ====================================================================

        # 累加到全局统计
        for k, v in current_stats.items():
            global_fleet_stats[k] += v

    # 计算 ALL -> ALL
    total_all = sum(global_fleet_stats.values())
    if total_all > 0:
        all_all_proportions = {k: v / total_all for k, v in global_fleet_stats.items()}
        fleet_proportions[("ALL", "ALL")] = all_all_proportions

    # ===== 追加：写入 Other -> Other（等权平均，排除前500条）=====
    if other_route_cnt > 0:
        other_other_proportions = {k: other_sum_props[k] / other_route_cnt for k in other_fleet_keys}
        fleet_proportions[("OTHER", "OTHER")] = other_other_proportions
    # ===========================================================

    save_fleet_proportions_to_csv(fleet_proportions)
    print("数据已保存到 fleet_proportions.csv")


if __name__ == "__main__":
    get_miu_main()