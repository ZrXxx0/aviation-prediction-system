from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import MacroEconomicIndicator, FlightStatRecord, PredictionRecord
from show.models import RouteMonthlyStat
from .serializers import MacroEconomicIndicatorSerializer, PredictionRecordSerializer, RouteMonthlyStatSerializer
from django.db.models import Sum

# 获取特定年份、城市经济数据
@api_view(['GET'])
def macro_indicator_view(request):
    city = request.GET.get('city')
    province = request.GET.get('province')
    year = request.GET.get('year')

    qs = MacroEconomicIndicator.objects.all()
    if city:
        qs = qs.filter(city=city)
    if province:
        qs = qs.filter(province=province)
    if year:
        qs = qs.filter(year=year)
    else:
        qs = qs.order_by('-year')[:1]  # 默认查最近一条

    if not qs.exists():
        return Response({"message": "无匹配数据"}, status=status.HTTP_404_NOT_FOUND)

    serializer = MacroEconomicIndicatorSerializer(qs, many=True)
    return Response(serializer.data)

# 获取最近五年城市的经济数据
@api_view(['GET'])
def macro_indicator_trend_view(request):
    city = request.GET.get('city')
    if not city:
        return Response({"error": "必须传入城市名 city"}, status=status.HTTP_400_BAD_REQUEST)

    # 查询该城市最近 5 年的数据
    qs = MacroEconomicIndicator.objects.filter(city=city).order_by("-year")[:5]
    qs = qs.order_by("year")  # 按时间升序排列

    if not qs.exists():
        return Response({"message": "未找到该城市的宏观经济数据"}, status=status.HTTP_404_NOT_FOUND)

    serializer = MacroEconomicIndicatorSerializer(qs, many=True)
    return Response({
        "city": city,
        "count": qs.count(),
        "data": serializer.data
    })


# 获取机型分布信息和 TOP10 城市运量
@api_view(["GET"])
def flight_statistics_view(request):
    origin = request.GET.get("origin")
    period = request.GET.get("period")  # 例如 "2024-07"
    period_type = request.GET.get("period_type", "monthly")  # 默认月度

    if not origin or not period:
        return Response({"error": "必须提供 origin 和 period"}, status=400)

    # 查询数据
    qs = FlightStatRecord.objects.filter(
        origin=origin,
        period__startswith=period,
        period_type=period_type
    )

    if not qs.exists():
        return Response({"message": "无匹配数据"}, status=404)

    # 1. 机型分布
    aircraft_distribution = qs.values("aircraft_type").annotate(
        total_capacity=Sum("available_capacity"),
        total_volume=Sum("actual_volume")
    )

    # 2. TOP10 城市运量
    top10_cities = (
        qs.values("destination")
        .annotate(total_volume=Sum("actual_volume"))
        .order_by("-total_volume")[:10]
    )

    return Response({
        "origin": origin,
        "period": period,
        "aircraft_distribution": list(aircraft_distribution),
        "top10_destinations": list(top10_cities),
    })

@api_view(['GET'])
def prediction_record_list(request):
    """
    查询预测历史记录（支持根据 origin、destination、时间筛选）
    """
    origin = request.GET.get("origin")
    destination = request.GET.get("destination")
    start = request.GET.get("start_date")
    end = request.GET.get("end_date")

    qs = PredictionRecord.objects.all()
    if origin:
        qs = qs.filter(origin__icontains=origin)
    if destination:
        qs = qs.filter(destination__icontains=destination)
    if start and end:
        qs = qs.filter(prediction_date__range=[start, end])

    qs = qs.order_by("-prediction_date")

    serializer = PredictionRecordSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
def route_stat_query(request):
    origin = request.GET.get('origin')
    destination = request.GET.get('destination')
    year = request.GET.get('year')
    month = request.GET.get('month')

    if not (origin and destination and year and month):
        return Response({"error": "请提供 origin、destination、year、month"}, status=status.HTTP_400_BAD_REQUEST)

    qs = RouteMonthlyStat.objects.filter(
        origin_city=origin,
        destination_city=destination,
        year=int(year),
        month=int(month)
    )

    if not qs.exists():
        return Response({"message": "无数据"}, status=404)

    serializer = RouteMonthlyStatSerializer(qs, many=True)
    return Response(serializer.data)

"""下面是看板部分所需的函数"""
# 获取过去10年数据
@api_view(['GET'])
def route_stat_yearly_total(request):
    origin = request.GET.get('origin')
    destination = request.GET.get('destination')

    if not (origin and destination):
        return Response({"error": "请提供 origin 和 destination"}, status=400)

    qs = RouteMonthlyStat.objects.filter(
        origin_city=origin,
        destination_city=destination
    )

    # 获取过去10年（如果数据很多就限制近10年）
    years = sorted(set(qs.values_list("year", flat=True)))
    if len(years) > 10:
        years = years[-10:]
        qs = qs.filter(year__in=years)

    result = (
        qs.values("year")
        .annotate(
            total_passenger_volume=Sum("passenger_volume"),
            total_seat_capacity=Sum("seat_capacity"),
            total_flight_count=Sum("flight_count"),
        )
        .order_by("year")
    )

    return Response(list(result))


# 获取最近的12个月的数据
@api_view(['GET'])
def route_stat_recent_12_months(request):
    origin = request.GET.get('origin')
    destination = request.GET.get('destination')

    if not (origin and destination):
        return Response({"error": "请提供 origin 和 destination"}, status=400)

    # 查询该航线的所有记录，按年+月倒序排列
    qs = RouteMonthlyStat.objects.filter(
        origin_city=origin,
        destination_city=destination
    ).order_by("-year", "-month")[:12]

    # 重新按升序排列以便图表展示（从最早到最近）
    qs = sorted(qs, key=lambda x: (x.year, x.month))

    # 返回最近十二个月的数据
    data = [
        {
            "year": q.year,
            "month": q.month,
            "label": f"{q.year}-{q.month:02d}",
            "passenger_volume": q.passenger_volume,   #
            "Route_Total_Seats": q.Route_Total_Seats,
            "Route_Total_Flights": q.Route_Total_Flights
        } for q in qs
    ]

    return Response({
        "origin": origin,
        "destination": destination,
        "data": data
    })