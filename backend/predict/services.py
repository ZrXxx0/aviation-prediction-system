from django.db.models import Sum
from predict.models import FlightMarketRecord
from show.models import RouteMonthlyStat
import pandas as pd


def sync_data_to_dashboard(affected_rows_data):
    """
    根据本次上传涉及的数据，聚合更新 Dashboard 表 (RouteMonthlyStat)
    affected_rows_data: list of dict, 本次插入/更新的原始数据
    """
    if not affected_rows_data:
        return

    # 1. 提取出所有涉及的 (Year, Month, Origin, Dest) 组合
    # 只需要这四个维度，因为 Dashboard 表是按航线聚合的，不区分 equipment
    keys_to_sync = set()
    for row in affected_rows_data:
        ym = row.get('year_month')  # "2024-01"
        origin = row.get('origin')
        dest = row.get('destination')

        if ym and origin and dest:
            try:
                # 解析 ym
                if isinstance(ym, str) and '-' in ym:
                    y_str, m_str = ym.split('-')[:2]
                    keys_to_sync.add((int(y_str), int(m_str), origin, dest))
            except:
                continue

    if not keys_to_sync:
        return

    print(f"🔄 开始同步看板数据，涉及 {len(keys_to_sync)} 条航线...")

    # 2. 针对每一条航线，重新从 FlightMarketRecord 聚合计算
    # 为什么要重新查库？因为本次上传可能只覆盖了某个机型，总数需要加上其他机型的数据
    to_update_or_create = []

    for year, month, origin, dest in keys_to_sync:
        ym_str = f"{year}-{month:02d}"

        # 聚合查询
        agg = FlightMarketRecord.objects.filter(
            year_month=ym_str,
            origin=origin,
            destination=dest
        ).aggregate(
            total_seats=Sum('equipment_total_seats'),
            total_flights=Sum('equipment_total_flights')
        )

        seats = agg['total_seats'] or 0
        flights = agg['total_flights'] or 0

        # 3. 准备写入 RouteMonthlyStat
        # 注意：这里需要根据你的 RouteMonthlyStat 实际字段调整
        # 假设字段是: year, month, origin_code, destination_code, Route_Total_Seats...

        # 查找或初始化对象
        stat_obj, created = RouteMonthlyStat.objects.get_or_create(
            year=year,
            month=month,
            origin_code=origin,
            destination_code=dest,
            defaults={
                'passenger_volume': 0,  # 默认值
                'Route_Total_Seats': seats,
                'Route_Total_Flights': flights
            }
        )

        # 如果是已存在的，更新数值
        if not created:
            stat_obj.Route_Total_Seats = seats
            stat_obj.Route_Total_Flights = flights
            to_update_or_create.append(stat_obj)

    # 4. 批量更新
    if to_update_or_create:
        RouteMonthlyStat.objects.bulk_update(
            to_update_or_create,
            ['Route_Total_Seats', 'Route_Total_Flights']
        )

    print("✅ 看板数据同步完成")