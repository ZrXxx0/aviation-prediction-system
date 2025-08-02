from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import RouteMonthlyStat
from .serializers import  RouteMonthlyStatSerializer
from django.db.models import Sum, Q
import os
import json
from collections import defaultdict

# 获得机场名和三字码映射
MAPPING_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_utils", "iata_city_airport_mapping.json")

try:
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        IATA_CITY_MAP = json.load(f)
    print(f"✅ 成功加载映射文件，共 {len(IATA_CITY_MAP)} 个机场")
except FileNotFoundError:
    IATA_CITY_MAP = {}
    print(f"⚠️ 未找到映射文件: {MAPPING_PATH}")

# 公共：根据 IATA 三字码构建映射信息
def build_info(iata_code):
    info = IATA_CITY_MAP.get(iata_code, {})
    return {
        "code": iata_code,
        "city": info.get("city"),
        "province": info.get("province"),
        "airport": info.get("airport")
    }

# 获取城市下的所有机场的三字码
def get_codes_by_city(city_name):
    codes = [
        code for code, info in IATA_CITY_MAP.items()
        if info.get("city") == city_name
    ]
    print(f"🔍 查找城市 '{city_name}' 的机场代码，找到: {codes}")
    return codes

# 获取城市名
def get_city_name(code):
    return IATA_CITY_MAP.get(code, {}).get("city")

# 根据机场三字码返回城市名和机场名
def get_city_airport(iata_code):
    info = IATA_CITY_MAP.get(iata_code, {})
    return info.get("city", iata_code), info.get("airport", iata_code)


"""下面是看板部分所需的函数"""
# 获取航线分布数据
@api_view(['GET'])
def route_distribution_view(request):
    year_month = request.GET.get("year_month")
    city = request.GET.get("city")  # 可为空
    print(f"🔍 接收到的参数 - year_month: {year_month}, city: {city}")
    
    if not year_month:
        return Response({"error": "请提供 year_month 参数"}, status=400)

    try:
        # 解析年月参数
        if '-' not in year_month:
            return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)
        
        year_str, month_str = year_month.split("-")
        year = int(year_str)
        month = int(month_str)
        
        print(f"🔍 解析后的时间参数 - year: {year}, month: {month}")
        
        # 验证月份范围
        if month < 1 or month > 12:
            return Response({"error": "月份必须在1-12之间"}, status=400)
            
    except ValueError as e:
        print(f"❌ 时间参数解析失败: {e}")
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)

    qs = RouteMonthlyStat.objects.filter(year=year, month=month)
    print(f"🔍 查询条件: year={year}, month={month}, 查询结果数量: {qs.count()}")

    # 情况一：指定起始城市
    if city:
        origin_codes = get_codes_by_city(city)
        if not origin_codes:
            return Response({"error": f"找不到城市 {city} 的三字码"}, status=404)
        qs = qs.filter(origin_code__in=origin_codes)
        print(f"🔍 筛选城市 {city}，机场代码: {origin_codes}")

        # 聚合按 destination city
        to_city_flights = defaultdict(int)
        for item in qs:
            to_city = get_city_name(item.destination_code) or item.destination_code
            to_city_flights[to_city] += item.Route_Total_Flights or 0

        result = [
            {"from": city, "to": to_city, "flights": flights}
            for to_city, flights in to_city_flights.items()
        ]
        # 按运量排序并取前100条
        result = sorted(result, key=lambda x: x["flights"], reverse=True)[:100]

    # 情况二：不指定城市，聚合所有城市对
    else:
        city_pair_flights = defaultdict(int)
        for item in qs:
            from_city = get_city_name(item.origin_code) or item.origin_code
            to_city = get_city_name(item.destination_code) or item.destination_code
            city_pair_flights[(from_city, to_city)] += item.Route_Total_Flights or 0

        result = [
            {"from": from_city, "to": to_city, "flights": flights}
            for (from_city, to_city), flights in city_pair_flights.items()
        ]
        # 按运量排序并取前100条
        result = sorted(result, key=lambda x: x["flights"], reverse=True)[:100]
    
    print(f"✅ 返回航线数据: {len(result)} 条记录")
    return Response(result)

# 获取统计卡片数据
# 若是全国，将所有城市聚合
@api_view(["GET"])
def statistics_summary_view(request):
    year_month = request.GET.get("year_month")
    start_city = request.GET.get("start_city")
    end_city = request.GET.get("end_city")

    print(f"🔍 接收到的参数 - year_month: {year_month}, start_city: {start_city}, end_city: {end_city}")

    # 参数校验
    if not year_month:
        return Response({"error": "请提供 year_month 参数"}, status=400)
    try:
        # 解析年月参数
        if '-' not in year_month:
            return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)
        
        year_str, month_str = year_month.split("-")
        year = int(year_str)
        month = int(month_str)
        
        print(f"🔍 解析后的时间参数 - year: {year}, month: {month}")
        
        # 验证月份范围
        if month < 1 or month > 12:
            return Response({"error": "月份必须在1-12之间"}, status=400)
            
    except ValueError as e:
        print(f"❌ 时间参数解析失败: {e}")
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)

    # 初始查询
    qs = RouteMonthlyStat.objects.filter(year=year, month=month)
    print(f"🔍 查询条件: year={year}, month={month}, 查询结果数量: {qs.count()}")

    # 起始城市筛选
    if start_city:
        origin_codes = get_codes_by_city(start_city)
        if not origin_codes:
            return Response({"error": f"未找到起始城市 {start_city} 的三字码"}, status=404)
        qs = qs.filter(origin_code__in=origin_codes)
        print(f"🔍 筛选起始城市 {start_city}，机场代码: {origin_codes}")

    # 终点城市筛选
    if end_city:
        destination_codes = get_codes_by_city(end_city)
        if not destination_codes:
            return Response({"error": f"未找到终点城市 {end_city} 的三字码"}, status=404)
        qs = qs.filter(destination_code__in=destination_codes)
        print(f"🔍 筛选终点城市 {end_city}，机场代码: {destination_codes}")

    # 聚合数据
    summary = qs.aggregate(
        capacity=Sum("Route_Total_Seats"),
        volume=Sum("passenger_volume"),
        flights=Sum("Route_Total_Flights"),
    )

    # 用默认值处理 None 情况
    result = {
        "capacity": int(summary["capacity"] or 0),
        "volume": int(summary["volume"] or 0),
        "flights": int(summary["flights"] or 0),
    }
    print(f"✅ 返回统计数据: {result}")
    return Response(result)

# 获取统计趋势数据
@api_view(['GET'])
def statistics_trend_view(request):
    year_month = request.GET.get("year_month")
    start_city = request.GET.get("start_city")
    end_city = request.GET.get("end_city")

    print(f"🔍 接收到的参数 - year_month: {year_month}, start_city: {start_city}, end_city: {end_city}")

    # 参数校验
    if not year_month:
        return Response({"error": "请提供 year_month 参数"}, status=400)
    try:
        # 解析年月参数
        if '-' not in year_month:
            return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)
        
        year_str, month_str = year_month.split("-")
        year = int(year_str)
        month = int(month_str)
        
        print(f"🔍 解析后的时间参数 - year: {year}, month: {month}")
        
        # 验证月份范围
        if month < 1 or month > 12:
            return Response({"error": "月份必须在1-12之间"}, status=400)
            
    except ValueError as e:
        print(f"❌ 时间参数解析失败: {e}")
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)

    qs = RouteMonthlyStat.objects.all()
    
    # 检查数据库中是否有数据
    total_count = RouteMonthlyStat.objects.count()
    print(f"🔍 数据库中总记录数: {total_count}")
    
    # 检查2024年6月的数据
    june_2024_count = RouteMonthlyStat.objects.filter(year=2024, month=6).count()
    print(f"🔍 2024年6月数据数量: {june_2024_count}")

    # 城市筛选
    if start_city:
        origin_codes = get_codes_by_city(start_city)
        if not origin_codes:
            return Response({"error": f"找不到城市 {start_city} 的三字码"}, status=404)
        qs = qs.filter(origin_code__in=origin_codes)
        print(f"🔍 筛选起始城市 {start_city}，机场代码: {origin_codes}")

    if end_city:
        dest_codes = get_codes_by_city(end_city)
        if not dest_codes:
            return Response({"error": f"找不到城市 {end_city} 的三字码"}, status=404)
        qs = qs.filter(destination_code__in=dest_codes)
        print(f"🔍 筛选终点城市 {end_city}，机场代码: {dest_codes}")

    # 计算起始年月（往前12个月）
    start_year = year
    start_month = month - 11
    if start_month <= 0:
        start_year -= 1
        start_month += 12

    # 筛选指定时间范围内的数据
    qs = qs.filter(
        (Q(year__gt=start_year) | 
        Q(year=start_year, month__gte=start_month)) &
        (Q(year__lt=year) | 
        Q(year=year, month__lte=month))
    )

    # 按年月排序
    qs = qs.order_by("year", "month")
    
    print(f"🔍 时间范围: {start_year}-{start_month:02d} 到 {year}-{month:02d}")
    print(f"🔍 查询结果数量: {qs.count()}")

    # 聚合按月
    monthly_data = {}
    for q in qs:
        key = f"{q.year}-{q.month:02d}"
        if key not in monthly_data:
            monthly_data[key] = {
                "capacity": 0,
                "volume": 0,
                "flights": 0
            }
        monthly_data[key]["capacity"] += int(q.Route_Total_Seats or 0)
        monthly_data[key]["volume"] += int(q.passenger_volume or 0)
        monthly_data[key]["flights"] += int(q.Route_Total_Flights or 0)

    # 构造返回结构
    months = []
    capacity = []
    volume = []
    flights = []

    for month_key in sorted(monthly_data.keys()):
        months.append(month_key)
        capacity.append(monthly_data[month_key]["capacity"])
        volume.append(monthly_data[month_key]["volume"])
        flights.append(monthly_data[month_key]["flights"])

    result = {
        "months": months,
        "capacity": capacity,
        "volume": volume,
        "flights": flights
    }
    print(f"✅ 返回趋势数据: {result}")

    return Response(result)