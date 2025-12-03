from django.conf import settings
from collections import OrderedDict
import datetime
import os
import csv
from collections import defaultdict
from django.core.wsgi import get_wsgi_application

# 设置 Django 配置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')

# 初始化 Django 应用
application = get_wsgi_application()
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


def get_market_data_for_route(origin, destination, year_months):
    """获取该航线所有月份的市场数据"""
    records = []
    for year_month in year_months:
        records += list(FlightMarketRecord.objects.filter(
            origin=origin, destination=destination, year_month=year_month
        ))
    return records


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


def get_fleet_proportions(records_for_fleet):
    fleet_stats = classify_fleet(records_for_fleet)
    total_flights = sum(fleet_stats.values())
    fleet_proportions = {fleet_type: flights / total_flights for fleet_type, flights in fleet_stats.items()}
    return fleet_proportions



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

def get_miu_main(limit: int = None):
    global fleet_mapping
    fleet_mapping = get_fleet_mapping()
    # print(fleet_mapping)
    # 获取前500条航线的OD
    routes = get_routes_from_csv(limit)

    # 获取前一年所有月份的列表
    one_year_ago = (datetime.datetime.now() - datetime.timedelta(days=365)).year
    year_months = [f"{one_year_ago}-{str(month).zfill(2)}" for month in range(1, 13)]

    # 初始化比例计算结果
    fleet_proportions = {}
    all_records = []
    for origin, destination in routes:
        # 获取该航线市场数据
        records_for_fleet = get_market_data_for_route(origin, destination, year_months)
        all_records.extend(records_for_fleet)
        # 计算各机型的比例
        fleet_proportions_for_route = get_fleet_proportions(records_for_fleet)
        # 将比例结果加入总体比例数据
        fleet_proportions[(origin, destination)] = fleet_proportions_for_route
        # ========= 新增：汇总所有航线，算一条 all -> all =========


    # 对所有记录重新按机队分类 + 计算比例（用的还是 seats 总和来算比例）
    all_all_proportions = get_fleet_proportions(all_records)



    # print(fleet_proportions)
    # 把 all→all 这一行加进结果里（最后插入，CSV 里就会在最后一行）
    fleet_proportions[("ALL", "ALL")] = all_all_proportions
    # ==========================================================
    # 保存结果到 CSV 文件
    save_fleet_proportions_to_csv(fleet_proportions)

    print("数据已保存到 fleet_proportions.csv")

if __name__ == "__main__":
    get_miu_main()