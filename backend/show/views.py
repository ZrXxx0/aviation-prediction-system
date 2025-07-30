from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import RouteMonthlyStat
from .serializers import  RouteMonthlyStatSerializer
from django.db.models import Sum
import os
import json
from collections import defaultdict

# 获得机场名和三字码映射
MAPPING_PATH = os.path.join(os.path.dirname(__file__), "iata_city_airport_mapping.json")

try:
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        IATA_CITY_MAP = json.load(f)
except FileNotFoundError:
    IATA_CITY_MAP = {}
    print("⚠️ 未找到 iata_city_airport_mapping.json，机场名/省份将无法映射")

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
    return [
        code for code, info in IATA_CITY_MAP.items()
        if info.get("city") == city_name
    ]

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

    if not year_month:
        return Response({"error": "请提供 year_month 参数"}, status=400)

    try:
        year, month = map(int, year_month.split("-"))
    except:
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2025-07"}, status=400)

    qs = RouteMonthlyStat.objects.filter(year=year, month=month)

    # 情况一：指定起始城市
    if city:
        origin_codes = get_codes_by_city(city)
        if not origin_codes:
            return Response({"error": f"找不到城市 {city} 的三字码"}, status=404)
        qs = qs.filter(origin_code__in=origin_codes)

        # 聚合按 destination city
        to_city_flights = defaultdict(int)
        for item in qs:
            to_city = get_city_name(item.destination_code) or item.destination_code
            to_city_flights[to_city] += item.Route_Total_Flights or 0

        result = [
            {"from": city, "to": to_city, "flights": flights}
            for to_city, flights in to_city_flights.items()
        ]

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

    return Response(result)

# 获取统计卡片数据
# 若是全国，将所有城市聚合
@api_view(["GET"])
def statistics_summary_view(request):
    year_month = request.GET.get("year_month")
    start_city = request.GET.get("start_city")
    end_city = request.GET.get("end_city")

    # 参数校验
    if not year_month:
        return Response({"error": "请提供 year_month 参数"}, status=400)
    try:
        year, month = map(int, year_month.split("-"))
    except:
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2025-07"}, status=400)

    # 初始查询
    qs = RouteMonthlyStat.objects.filter(year=year, month=month)

    # 起始城市筛选
    if start_city:
        origin_codes = get_codes_by_city(start_city)
        if not origin_codes:
            return Response({"error": f"未找到起始城市 {start_city} 的三字码"}, status=404)
        qs = qs.filter(origin_code__in=origin_codes)

    # 终点城市筛选
    if end_city:
        destination_codes = get_codes_by_city(end_city)
        if not destination_codes:
            return Response({"error": f"未找到终点城市 {end_city} 的三字码"}, status=404)
        qs = qs.filter(destination_code__in=destination_codes)

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

    return Response(result)

# 获取统计趋势数据
@api_view(['GET'])
def statistics_trend_view(request):
    start_city = request.GET.get("start_city")
    end_city = request.GET.get("end_city")

    qs = RouteMonthlyStat.objects.all()

    # 城市筛选
    if start_city:
        origin_codes = get_codes_by_city(start_city)
        if not origin_codes:
            return Response({"error": f"找不到城市 {start_city} 的三字码"}, status=404)
        qs = qs.filter(origin_code__in=origin_codes)

    if end_city:
        dest_codes = get_codes_by_city(end_city)
        if not dest_codes:
            return Response({"error": f"找不到城市 {end_city} 的三字码"}, status=404)
        qs = qs.filter(destination_code__in=dest_codes)

    # 仅获取最近12个月
    qs = qs.order_by("-year", "-month")[:12]
    qs = list(qs)  # 转成列表以便排序
    qs.sort(key=lambda x: (x.year, x.month))  # 升序排列

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

    for month in sorted(monthly_data.keys()):
        months.append(month)
        capacity.append(monthly_data[month]["capacity"])
        volume.append(monthly_data[month]["volume"])
        flights.append(monthly_data[month]["flights"])

    return Response({
        "months": months,
        "capacity": capacity,
        "volume": volume,
        "flights": flights
    })