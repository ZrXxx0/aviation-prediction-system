from django.conf import settings
from collections import OrderedDict
import datetime
import os
import csv
from django.db.models import Q
from collections import defaultdict
from predict.models import FlightMarketRecord,FleetParam

# 配置路径
ROUTE_RANKING_CSV = os.path.join(
    settings.BASE_DIR, "Predict_Datas", "route_ranking.csv"
)


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
    if not os.path.exists(ROUTE_RANKING_CSV):
        print(f"CSV file does not exist: {ROUTE_RANKING_CSV}")
        return routes

    # 打开并读取 CSV 文件
    with open(ROUTE_RANKING_CSV, newline="", encoding="utf-8") as f:
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
    fleet_stats = defaultdict(int)
    for record in records_for_fleet:
        flights = float(record.equipment_total_flights or 0)
        seats = float(record.equipment_total_seats or 0)

        if flights > 0 and seats > 0:
            avg_seats = seats / flights
            fleet_type = None

            for fleet_name, threshold in fleet_mapping.items():
                if avg_seats <= threshold:
                    fleet_type = fleet_name
                    break

            if fleet_type is None:
                fleet_type = "大型宽体客机"

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
        "大型涡扇支线客机",
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
        "大型涡扇支线客机": 76,
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
    data_map = defaultdict(list)

    # Process in batches
    for i in range(0, len(routes), batch_size):
        batch_routes = routes[i: i + batch_size]

        q_objects = Q()
        for origin, dest in batch_routes:
            q_objects |= Q(origin=origin, destination=dest)

        # Execute query for this batch
        records = FlightMarketRecord.objects.filter(q_objects, year_month__in=year_months)

        for record in records:
            data_map[(record.origin, record.destination)].append(record)

    return data_map


def get_miu_main(limit: int = None):
    global fleet_mapping
    fleet_mapping = get_fleet_mapping()

    print("正在读取航线...")
    routes = get_routes_from_csv(limit)
    if not routes:
        print("未找到航线，退出。")
        return

    one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).year
    year_months = [f"{one_year_ago}-{str(month).zfill(2)}" for month in range(1, 13)]

    print(f"正在批量获取数据库数据 (Routes: {len(routes)})...")
    # 优化1：批量获取数据，而不是循环查库
    # 注意：如果 routes 数量特别巨大（如超过2000），建议分批次处理（batch），这里假设数量适中
    records_map = get_market_data_bulk(routes, year_months)
    print("数据库查询完成，开始计算比例...")

    fleet_proportions = {}

    # 优化2：不再存储 all_records 对象列表，而是累加统计数值
    global_fleet_stats = defaultdict(int)

    total_count = len(routes)

    for idx, (origin, destination) in enumerate(routes, 1):
        # 打印进度条
        if idx % 100 == 0:
            print(f"Processing {idx}/{total_count}...")

        # 从内存字典里取数据，不查库
        records_for_fleet = records_map.get((origin, destination), [])

        if not records_for_fleet:
            continue

        # 计算单条航线比例
        # 这里我们需要稍微修改 classify_fleet，让它返回 stats 字典，而不是在内部消化
        current_stats = classify_fleet(records_for_fleet)  # 复用你现有的逻辑

        # 计算比例
        total_f = sum(current_stats.values())
        if total_f > 0:
            props = {k: v / total_f for k, v in current_stats.items()}
            fleet_proportions[(origin, destination)] = props

        # 累加到全局统计 (替代 all_records)
        for k, v in current_stats.items():
            global_fleet_stats[k] += v

    # 计算 ALL -> ALL
    total_all = sum(global_fleet_stats.values())
    if total_all > 0:
        all_all_proportions = {k: v / total_all for k, v in global_fleet_stats.items()}
        fleet_proportions[("ALL", "ALL")] = all_all_proportions

    save_fleet_proportions_to_csv(fleet_proportions)
    print("数据已保存到 fleet_proportions.csv")

if __name__ == "__main__":
    get_miu_main()