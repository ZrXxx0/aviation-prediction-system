from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import RouteMonthlyStat, AirportInfo
from .serializers import  RouteMonthlyStatSerializer
from django.db.models import Sum, Q, Count
from django.core.exceptions import ObjectDoesNotExist
import os
import json
from collections import defaultdict

# 公共：根据 IATA 三字码构建映射信息（从数据库获取）
def build_info(iata_code):
    try:
        info = AirportInfo.objects.get(code=iata_code.upper())
        return {
            "code": info.code,
            "city": info.city,
            "province": info.province,
            "airport": info.airport
        }
    except ObjectDoesNotExist:
        return {
            "code": iata_code,
            "city": None,
            "province": None,
            "airport": None
        }

# 获取城市下的所有机场的三字码
def get_codes_by_city(city_name):
    codes = list(
        AirportInfo.objects.filter(city=city_name).values_list("code", flat=True)
    )
    print(f"🔍 查找城市 '{city_name}' 的机场代码，找到: {codes}")
    return codes

# 获取城市名
def get_city_name(code):
    try:
        return AirportInfo.objects.get(code=code.upper()).city
    except ObjectDoesNotExist:
        return None

# 根据机场三字码返回城市名和机场名
def get_city_airport(iata_code):
    try:
        info = AirportInfo.objects.get(code=iata_code.upper())
        return info.city, info.airport
    except ObjectDoesNotExist:
        return iata_code, iata_code


"""下面是看板部分所需的函数"""
# 获取航线分布数据
@api_view(['GET'])
def route_distribution_view(request):
    """
    获取航线分布数据（支持起始城市与到达城市可选过滤）
    - year_month: 必填，YYYY-MM
    - city: 必填，起始城市（"全国"表示不限制起始城市）
    - to_city: 必填，到达城市（"全国"表示不限制到达城市）
    
    逻辑说明：
    1. 如果city和to_city都是"全国"：查询全国前100航线
    2. 如果city不是"全国"，to_city是"全国"：查询以city为起点的前100航线
    3. 如果city是"全国"，to_city不是"全国"：查询目的城市是to_city的前100航线
    4. 如果city和to_city都不是"全国"：查询两个城市之间的航线
    """
    year_month = request.GET.get("year_month")
    origin_city = request.GET.get("city")      # 起始城市
    dest_city = request.GET.get("to_city")     # 到达城市

    print(f"🔍 接收到参数 year_month={year_month}, city={origin_city}, to_city={dest_city}")

    # 参数验证
    if not year_month or '-' not in year_month:
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)
    
    if not origin_city or not dest_city:
        return Response({"error": "city 和 to_city 参数都是必填的"}, status=400)

    try:
        year_str, month_str = year_month.split("-")
        year = int(year_str); month = int(month_str)
        if not (1 <= month <= 12):
            return Response({"error": "月份必须在1-12之间"}, status=400)
    except ValueError:
        return Response({"error": "year_month 格式应为 YYYY-MM，如 2024-06"}, status=400)

    # ---- 组装过滤条件 ----
    filters = {"year": year, "month": month, "Route_Total_Flights__gt": 0}

    # 处理起始城市过滤
    if origin_city != "全国":
        origin_codes = get_codes_by_city(origin_city)
        if not origin_codes:
            return Response({"error": f"找不到起始城市 {origin_city} 的三字码"}, status=404)
        filters["origin_code__in"] = origin_codes

    # 处理到达城市过滤
    if dest_city != "全国":
        dest_codes = get_codes_by_city(dest_city)
        if not dest_codes:
            return Response({"error": f"找不到到达城市 {dest_city} 的三字码"}, status=404)
        filters["destination_code__in"] = dest_codes

    print(f"🔎 最终查询条件: {filters}")

    # 仅取必要字段，减少内存
    route_rows = list(
        RouteMonthlyStat.objects
        .filter(**filters)
        .values("origin_code", "destination_code", "Route_Total_Flights")
    )
    print(f"📦 取到有效航线条数: {len(route_rows)}")
    if not route_rows:
        return Response([])

    # 批量拿机场信息（避免 N+1）
    codes = {r["origin_code"] for r in route_rows} | {r["destination_code"] for r in route_rows}
    info_map = {}
    if codes:
        for a in AirportInfo.objects.filter(code__in=codes):
            info_map[a.code] = {"code": a.code, "city": a.city, "province": a.province, "airport": a.airport}

    # 聚合：城市对总航班量 & 机场对明细
    city_pair_total = defaultdict(int)
    city_pair_detail = defaultdict(list)

    for r in route_rows:
        o = info_map.get(r["origin_code"], {"code": r["origin_code"], "city": None, "province": None, "airport": None})
        d = info_map.get(r["destination_code"], {"code": r["destination_code"], "city": None, "province": None, "airport": None})
        flights = r["Route_Total_Flights"] or 0
        if flights <= 0:
            continue

        key = (o["city"], d["city"])
        city_pair_total[key] += flights
        city_pair_detail[key].append({
            "from_airport": o["airport"],
            "to_airport": d["airport"],
            "flights": flights
        })

    # 构建结果：按总航班量倒序取前100
    sorted_pairs = sorted(city_pair_total.items(), key=lambda x: x[1], reverse=True)[:100]
    result = [
        {
            "from": fc,
            "to": tc,
            "flights": total,
            "detail": sorted(city_pair_detail[(fc, tc)], key=lambda x: x["flights"], reverse=True)
        }
        for (fc, tc), total in sorted_pairs
    ]

    print(f"✅ 返回航线数据: {len(result)} 条")
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