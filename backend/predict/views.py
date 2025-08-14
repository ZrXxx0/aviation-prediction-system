from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json
import pandas as pd
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.core.exceptions import ObjectDoesNotExist
from .models import MacroEconomicIndicator, FlightStatRecord, PredictionRecord
from show.models import RouteMonthlyStat
from .serializers import MacroEconomicIndicatorSerializer, PredictionRecordSerializer, RouteMonthlyStatSerializer
from django.db.models import Sum
from .predictive_algorithm.predict import forecast_from_files
from .models import RouteModelInfo
from show.models import AirportInfo


def _to_bool(s: str, default=True):
    if s is None:
        return default
    return str(s).lower() in ("1", "true", "t", "yes", "y")

# --- 工具：城市 -> 机场三字码列表（来自 show.AirportInfo）---
def get_codes_by_city(city_name: str):
    return list(
        AirportInfo.objects.filter(city=city_name).values_list("code", flat=True)
    )

# --- 工具：三字码 -> 城市/机场信息（来自 show.AirportInfo）---
def build_info(iata_code: str):
    try:
        a = AirportInfo.objects.get(code=iata_code.upper())
        return {"code": a.code, "city": a.city, "province": a.province, "airport": a.airport}
    except ObjectDoesNotExist:
        return {"code": iata_code, "city": None, "province": None, "airport": None}

def _fmt_label(dt_like, granularity: str) -> str:
    """把日期按粒度转成横轴标签"""
    d = pd.to_datetime(dt_like, errors="coerce")
    if pd.isna(d):
        return str(dt_like)
    if granularity == "yearly":
        return f"{d.year}年"
    if granularity == "quarterly":
        q = (d.month - 1) // 3 + 1
        return f"{d.year}-Q{q}"
    return d.strftime("%Y-%m")

# 预测函数
@require_GET
def forecast_batch_chart_view(request):
    """
    批量预测（多航线、多套参数），按 timeLabels/series/performance 返回：
    GET /api/forecast-chart?jobs=[{...},{...}]
    jobs 例子：
    [
      {"timeRange":"monthly","numFeatures":12,"modelType":"lgb","fromCity":"北京","toCity":"上海","showTrain":true},
      {"timeRange":"quarterly","numFeatures":6,"modelType":"lgb","fromCity":"广州","toCity":"北京","showTrain":false}
    ]

    若无 jobs，则兼容单套参数：
    /api/forecast-chart?timeRange=monthly&numFeatures=12&modelType=lgb&fromCity=北京&toCity=上海&showTrain=true
    """
    try:
        # 1) 解析 jobs（批量优先；否则单条兜底）
        jobs_param = request.GET.get("jobs")
        if jobs_param:
            try:
                jobs = json.loads(jobs_param)
                if not isinstance(jobs, list):
                    return JsonResponse({"error": "jobs 必须是 JSON 数组"}, status=400)
            except Exception:
                return JsonResponse({"error": "jobs 需为合法 JSON 数组"}, status=400)
        else:
            jobs = [{
                "timeRange": request.GET.get("timeRange", "monthly"),
                "numFeatures": request.GET.get("numFeatures", 12),
                "modelType": request.GET.get("modelType", "lgb"),
                "fromCity": request.GET.get("fromCity"),
                "toCity": request.GET.get("toCity"),
                "showTrain": _to_bool(request.GET.get("showTrain"), True),
            }]

        payloads, errors = [], []

        # 2) 逐 job 处理
        for idx, job in enumerate(jobs, start=1):
            # ---- 参数读取 & 校验 ----
            time_range = (job.get("timeRange") or "monthly").lower()
            model_type = job.get("modelType", "lgb")  # 目前不参与筛选，仅占位
            try:
                num_features = int(job.get("numFeatures", 12))
            except Exception:
                errors.append({"index": idx, "error": "numFeatures 必须为整数"})
                continue
            from_city = job.get("fromCity")
            to_city   = job.get("toCity")
            show_train = _to_bool(job.get("showTrain"), True)

            if not from_city or not to_city:
                errors.append({"index": idx, "error": "fromCity / toCity 不能为空"})
                continue
            if time_range not in ("monthly", "quarterly", "yearly"):
                errors.append({"index": idx, "error": "timeRange 仅支持 monthly/quarterly/yearly"})
                continue
            if num_features <= 0:
                errors.append({"index": idx, "error": "numFeatures 必须为正整数"})
                continue

            # ---- 城市 -> 三字码 ----
            origin_codes = get_codes_by_city(from_city)
            dest_codes   = get_codes_by_city(to_city)
            if not origin_codes:
                errors.append({"index": idx, "route": f"{from_city}->{to_city}", "error": f"未找到起点城市 {from_city} 的机场三字码"})
                continue
            if not dest_codes:
                errors.append({"index": idx, "route": f"{from_city}->{to_city}", "error": f"未找到终点城市 {to_city} 的机场三字码"})
                continue

            # ---- 模型：粒度 + 码集合，取最新 ----
            qs = (
                RouteModelInfo.objects
                .filter(
                    time_granularity=time_range,
                    origin_airport__in=origin_codes,
                    destination_airport__in=dest_codes,
                )
                .order_by("-train_datetime")
            )
            if not qs.exists():
                errors.append({"index": idx, "route": f"{from_city}->{to_city}", "error": f"未找到该航线（粒度 {time_range}）的已训练模型"})
                continue

            m = qs.first()

            # ---- 调用你的预测函数（会保存 prediction_results_{numFeatures}.csv）----
            df = forecast_from_files(
                meta_file_path=m.meta_file_path,
                model_file_path=m.model_file_path,
                raw_data_file_path=m.raw_data_file_path,
                preprocessor_file_path=m.preprocessor_file_path,
                feature_builder_file_path=m.feature_builder_file_path,
                showTrain=show_train,
                numFeatures=num_features,
                save_data=True,
            )

            # ---- 统一处理 forecast_from_files 的返回 ----
            df = df.copy()
            # 1) 确保时间类型并排序
            df["YearMonth"] = pd.to_datetime(df["YearMonth"], errors="coerce")
            df = df.dropna(subset=["YearMonth"]).sort_values("YearMonth").reset_index(drop=True)

            # 2) 生成 timeLabels
            if show_train:
                # 全段（Train+Test+Future）
                labels = [_fmt_label(x, time_range) for x in df["YearMonth"]]
            else:
                # 只未来
                fpart = df[df["Set"] == "Future"]
                labels = [_fmt_label(x, time_range) for x in fpart["YearMonth"]]

            # 3) 组装 series（历史为实线，未来为虚线；或仅未来）
            o_info = build_info(m.origin_airport)
            d_info = build_info(m.destination_airport)
            line_name = f"{o_info.get('city') or m.origin_airport} → {d_info.get('city') or m.destination_airport}"

            if show_train:
                hist_mask = df["Set"].isin(["Train", "Test"])
                fut_mask  = df["Set"].eq("Future")
                series = [
                    {
                        "name": line_name,
                        "type": "line",
                        "smooth": True,
                        "data": [None if pd.isna(v) else float(v) for v in df["Predicted"].where(hist_mask)],
                        "lineStyle": {"type": "solid"},
                    },
                    {
                        "name": line_name,
                        "type": "line",
                        "smooth": True,
                        "data": [None if pd.isna(v) else float(v) for v in df["Predicted"].where(fut_mask)],
                        "lineStyle": {"type": "dashed"},
                    },
                ]
            else:
                fpart = df[df["Set"] == "Future"]
                series = [{
                    "name": line_name,
                    "type": "line",
                    "smooth": True,
                    "data": [None if pd.isna(v) else float(v) for v in fpart["Predicted"]],
                    "lineStyle": {"type": "solid"},
                }]

            # 4) performance：优先用测试集指标，缺失则降级训练集
            def _fmt(v, nd=2):
                if v is None:
                    return None
                try:
                    return f"{float(v):.{nd}f}"
                except Exception:
                    return None

            r2   = m.test_r2  if m.test_r2  is not None else m.train_r2
            mape = m.test_mape if m.test_mape is not None else m.train_mape
            rmse = m.test_rmse if m.test_rmse is not None else m.train_rmse

            performance = [{
                "route": line_name,
                "model": model_type,
                "r2":   _fmt(r2, 3),
                "mape": _fmt(mape, 2),
                "rmse": _fmt(rmse, 2),
            }]

            # 5) 单 job 的 payload
            payloads.append({
                "timeLabels": labels,
                "series": series,
                "performance": performance,
                "meta": {  # 方便前端展示或排查
                    "timeRange": time_range,
                    "numFeatures": num_features,
                    "model_id": m.model_id,
                    "trained_at": m.train_datetime,
                    "origin": o_info,
                    "destination": d_info,
                }
            })

        # 3) 返回：若只有1套且无错误 -> 直接返回 payload；否则返回 {payloads, errors}
        if len(payloads) == 1 and not errors:
            return JsonResponse(payloads[0], json_dumps_params={"ensure_ascii": False})
        return JsonResponse({"payloads": payloads, "errors": errors}, json_dumps_params={"ensure_ascii": False})

    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

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