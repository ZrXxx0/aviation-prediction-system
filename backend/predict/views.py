import os
import json
import pandas as pd
import numpy as np
import math
from datetime import datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from typing import Optional
import copy
from decimal import Decimal
from collections import OrderedDict
from .models import RouteModelInfo, PretrainRecord, FlightMarketRecord, ForecastUpdateLog,ForecastMonthly, ForecastQuarterly, ForecastYearly, FleetParam
from show.models import AirportInfo
from .predictive_algorithm.pretrain_single_route import pretrain_single_route
from .predictive_algorithm.predict_single_route import predict_single_route
from predict.predictive_algorithm.hierarchical_alignment import aggregate_quarterly_to_year_by_blocks,linear_reconcile_monthly_to_quarterly,mint_reconcile_monthly_to_quarterly
from .predictive_algorithm.fromal_train_single_route import formal_train_single_route

import warnings
warnings.filterwarnings("ignore")

# 添加正确的导入路径，解决pickle加载时的模块依赖问题
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
predictive_algorithm_dir = os.path.join(current_dir, 'predictive_algorithm')
if predictive_algorithm_dir not in sys.path:
    sys.path.insert(0, predictive_algorithm_dir)

# --- 辅助：标准化日期成 YYYY-MM ---
def _to_year_month(s: Optional[str]):
    if not s:
        return None
    s = s.strip()
    return s[:7] if len(s) >= 7 else s

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

def clean_nan_values(data_dict):
    """
    清理字典中的nan值，将nan替换为None，并确保所有数值都是JSON兼容的
    """
    cleaned_data = {}
    for key, value in data_dict.items():
        if value is None:
            cleaned_data[key] = None
        elif isinstance(value, (int, float)):
            # 检查是否为nan或inf
            if hasattr(np, 'isnan') and np.isnan(value):
                cleaned_data[key] = None
            elif hasattr(np, 'isinf') and np.isinf(value):
                cleaned_data[key] = None
            else:
                # 确保数值在JSON范围内
                if value > 1e308 or value < -1e308:
                    cleaned_data[key] = None
                else:
                    cleaned_data[key] = float(value)
        elif isinstance(value, np.floating):
            # 处理numpy浮点数
            if np.isnan(value) or np.isinf(value):
                cleaned_data[key] = None
            else:
                # 转换为Python float并检查范围
                float_val = float(value)
                if float_val > 1e308 or float_val < -1e308:
                    cleaned_data[key] = None
                else:
                    cleaned_data[key] = float_val
        elif isinstance(value, np.integer):
            # 处理numpy整数
            cleaned_data[key] = int(value)
        else:
            cleaned_data[key] = value
    return cleaned_data

import re
from datetime import datetime, date
def attach_existing_ask_predictions(item):
    """
    根据 item 中的 model_info / prediction_results.future_predictions，
    去 ForecastMonthly/Quarterly/Yearly 表里查已有 ASK，
    并添加到 prediction_results.exit_predictions 中。

    time_granularity 决定：
      - 使用哪个 ForecastXXX 模型
      - time_point 的解析规则（带“缓和模式”）
    """
    try:
        model_info = item.get('model_info') or {}
        pr = item.get('prediction_results') or {}

        gran = model_info.get('time_granularity')
        origin = model_info.get('origin_airport')
        dest = model_info.get('destination_airport')

        if not (gran and origin and dest):
            return item

        # 只看 future_predictions
        future_list = pr.get('future_predictions') or []
        time_points = [r.get('time_point') for r in future_list if r.get('time_point')]
        if not time_points:
            return item

        # --------- 宽松解析 time_point -> forecast_date ----------
        def tp_to_date(tp: str) -> date:
            """
            支持的例子：

            yearly:
              "2024"
              "2024-1" / "2024-01"
              "2024-1-1" / "2024-01-01"

            quarterly:
              "2024-Q1"
              "2024-1" / "2024-4"  (按月份推所属季度)
              "2024-01-01" 等完整日期（按月份推季度）

            monthly:
              "2024-06"
              "2024-06-01"
            """
            s = tp.strip()

            # ===== 月度 =====
            if gran == 'monthly':
                for fmt in ('%Y-%m', '%Y-%m-%d'):
                    try:
                        dt = datetime.strptime(s, fmt).date()
                        return dt.replace(day=1)
                    except ValueError:
                        continue
                raise ValueError(f'不支持的月度时间格式: {tp}')

            # ===== 年度 =====
            elif gran == 'yearly':
                # 从字符串里提取第一个 4 位数字当作年份，支持 "2023年" 这种
                m = re.search(r'(\d{4})', s)
                if m:
                    year = int(m.group(1))
                    return date(year, 1, 1)
                raise ValueError(f'不支持的年度时间格式: {tp}')


            # ===== 季度 =====
            elif gran == 'quarterly':
                # 1) 新格式: "2024-Q1"
                m = re.match(r'^(\d{4})-Q([1-4])$', s, re.IGNORECASE)
                if m:
                    year = int(m.group(1))
                    q = int(m.group(2))
                    start_month = (q - 1) * 3 + 1
                    return date(year, start_month, 1)

                # 2) 老格式: "2024-1" / "2024-4" 之类，把后面的数当月份
                m = re.match(r'^(\d{4})-(\d{1,2})$', s)
                if m:
                    year = int(m.group(1))
                    month = int(m.group(2))
                    q = (month - 1) // 3 + 1          # 所属季度
                    start_month = (q - 1) * 3 + 1    # 季度起始月
                    return date(year, start_month, 1)

                # 3) 完整日期: "2024-01-01" 之类
                try:
                    dt = datetime.strptime(s, '%Y-%m-%d').date()
                    month = dt.month
                    q = (month - 1) // 3 + 1
                    start_month = (q - 1) * 3 + 1
                    return date(dt.year, start_month, 1)
                except ValueError:
                    pass

                raise ValueError(f'不支持的季度时间格式: {tp}')

            # 其他粒度兜底
            else:
                for fmt in ('%Y-%m-%d', '%Y-%m'):
                    try:
                        return datetime.strptime(s, fmt).date()
                    except ValueError:
                        continue
                raise ValueError(f'不支持的时间格式: {tp}')

        # time_point -> forecast_date
        point_date_map = {tp: tp_to_date(tp) for tp in time_points}
        date_list = list(point_date_map.values())

        # 选择对应的 ForecastXXX 模型
        if gran == 'monthly':
            ModelCls = ForecastMonthly
        elif gran == 'quarterly':
            ModelCls = ForecastQuarterly
        elif gran == 'yearly':
            ModelCls = ForecastYearly
        else:
            return item

        qs = ModelCls.objects.filter(
            origin=origin,
            destination=dest,
            forecast_date__in=date_list,
        ).values('forecast_date', 'ask')

        ask_map = {row['forecast_date']: row['ask'] for row in qs}

        # exit_predictions：与 future_predictions 一一对应
        exit_predictions = []
        for r in future_list:
            tp = r.get('time_point')
            if not tp:
                continue
            fd = point_date_map.get(tp)
            ask_val = ask_map.get(fd)  # 查不到就是 None
            exit_predictions.append({
                'time_point': tp,
                'value': ask_val,
            })

        pr['exit_predictions'] = exit_predictions
        item['prediction_results'] = pr
        return item

    except Exception:
        # 不让它影响主流程，有需要你可以改成 logging
        return item

def parse_forecast_date(granularity: str, s: str) -> date:
    """
    根据 time_granularity 把前端传来的 forecast_date 字符串
    解析成真正存库用的 Date 对象。

    支持的示例（可以混用）：

    monthly:
      "2024-06"
      "2024-06-01"

    yearly:
      "2024"
      "2024-1" / "2024-01"
      "2024-1-1" / "2024-01-01"

    quarterly:
      "2024-Q1"
      "2024-1" / "2024-4"  -> 把后面的当“月份”，按月份推所属季度
      "2024-01-01"        -> 按月份推所属季度

    解析结果：
      - monthly   -> 该月 1 号
      - quarterly -> 该季度起始月的 1 号
      - yearly    -> 当年 1 月 1 号
    """
    s = (s or "").strip()
    if not s:
        raise ValueError("forecast_date 不能为空")

    # ===== 月度 =====
    if granularity == "monthly":
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                dt = datetime.strptime(s, fmt).date()
                return dt.replace(day=1)
            except ValueError:
                continue
        raise ValueError(f"不支持的月度时间格式: {s}（推荐 2024-06 或 2024-06-01）")

    # ===== 年度 =====
    if granularity == "yearly":
        # 纯年份: "2024"
        if s.isdigit() and len(s) == 4:
            return date(int(s), 1, 1)

        # "2024-1-1" / "2024-01-01" / "2024-1" / "2024-01"
        for fmt in ("%Y-%m-%d", "%Y-%m"):
            try:
                dt = datetime.strptime(s, fmt).date()
                return date(dt.year, 1, 1)
            except ValueError:
                continue

        raise ValueError(f"不支持的年度时间格式: {s}（推荐 2024 或 2024-01-01）")

    # ===== 季度 =====
    if granularity == "quarterly":
        # 1) "2024-Q1"
        m = re.match(r"^(\d{4})-Q([1-4])$", s, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            q = int(m.group(2))
            start_month = (q - 1) * 3 + 1
            return date(year, start_month, 1)

        # 2) "2024-1" / "2024-4" -> 按月份推季度
        m = re.match(r"^(\d{4})-(\d{1,2})$", s)
        if m:
            year = int(m.group(1))
            month = int(m.group(2))
            q = (month - 1) // 3 + 1
            start_month = (q - 1) * 3 + 1
            return date(year, start_month, 1)

        # 3) "2024-01-01" -> 用日期的月份推季度
        try:
            dt = datetime.strptime(s, "%Y-%m-%d").date()
            month = dt.month
            q = (month - 1) // 3 + 1
            start_month = (q - 1) * 3 + 1
            return date(dt.year, start_month, 1)
        except ValueError:
            pass

        raise ValueError(f"不支持的季度时间格式: {s}（推荐 2024-Q1 或 2024-01-01）")

    # 兜底：如果粒度写错了，这里也试着按日期解析
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"不支持的时间格式: {s}")


# 获取预测模型函数
@api_view(['GET'])
def get_forecast_models(request):
    """
    获取可用于预测的模型列表
    
    参数：
    - origin_airport: 起点机场三字码
    - destination_airport: 终点机场三字码  
    - time_granularity: 时间粒度 (yearly/quarterly/monthly)
    
    返回：
    - 按模型质量排序的模型列表，每个模型包含：
      - model_id: 模型ID
      - 8个评估指标 (train_mae, train_rmse, train_mape, train_r2, test_mae, test_rmse, test_mape, test_r2)
      - train_start_time: 训练开始时间
      - train_end_time: 训练结束时间
    """
    try:
        # 获取查询参数
        origin_airport = request.GET.get('origin_airport', '').upper()
        destination_airport = request.GET.get('destination_airport', '').upper()
        time_granularity = request.GET.get('time_granularity', '')
        
        # 参数验证
        if not origin_airport or not destination_airport or not time_granularity:
            return JsonResponse({
                'error': '缺少必要参数',
                'message': '请提供 origin_airport, destination_airport 和 time_granularity 参数'
            }, status=400)
        
        if time_granularity not in ['yearly', 'quarterly', 'monthly']:
            return JsonResponse({
                'error': '无效的时间粒度',
                'message': 'time_granularity 必须是 yearly, quarterly 或 monthly 之一'
            }, status=400)
        
        # 查询匹配的模型
        models = RouteModelInfo.objects.filter(
            origin_airport=origin_airport,
            destination_airport=destination_airport,
            time_granularity=time_granularity
        )
        
        if not models.exists():
            return JsonResponse({
                'success': True,
                'data': None
            })
        
        # 计算每个模型的综合评分（用于排序）
        model_list = []
        for model in models:
            # 使用测试集指标作为主要评估标准，训练集指标作为辅助
            # 综合评分 = (1 - test_mape) * 0.4 + test_r2 * 0.3 + (1 - test_mae/1000) * 0.2 + (1 - test_rmse/1000) * 0.1
            # 这里假设MAE和RMSE的合理范围在1000以内，实际使用时可能需要根据数据特点调整
            
            test_mae_score = 0 if model.test_mae is None else max(0, 1 - model.test_mae / 1000)
            test_rmse_score = 0 if model.test_rmse is None else max(0, 1 - model.test_rmse / 1000)
            test_mape_score = 0 if model.test_mape is None else max(0, 1 - model.test_mape / 100)
            test_r2_score = 0 if model.test_r2 is None else max(0, model.test_r2)
            
            # 如果测试集指标缺失，使用训练集指标
            if model.test_mae is None and model.train_mae is not None:
                test_mae_score = max(0, 1 - model.train_mae / 1000)
            if model.test_rmse is None and model.train_rmse is not None:
                test_rmse_score = max(0, 1 - model.train_rmse / 1000)
            if model.test_mape is None and model.train_mape is not None:
                test_mape_score = max(0, 1 - model.train_mape / 100)
            if model.test_r2 is None and model.train_r2 is not None:
                test_r2_score = max(0, model.train_r2)
            
            # 计算综合评分
            composite_score = (
                test_mape_score * 0.4 + 
                test_r2_score * 0.3 + 
                test_mae_score * 0.2 + 
                test_rmse_score * 0.1
            )
            
            model_info = {
                'model_id': model.model_id,
                'train_mae': model.train_mae,
                'train_rmse': model.train_rmse,
                'train_mape': model.train_mape,
                'train_r2': model.train_r2,
                'test_mae': model.test_mae,
                'test_rmse': model.test_rmse,
                'test_mape': model.test_mape,
                'test_r2': model.test_r2,
                'train_start_time': model.train_start_time.strftime('%Y-%m-%d') if model.train_start_time else None,
                'train_end_time': model.train_end_time.strftime('%Y-%m-%d') if model.train_end_time else None,
                'composite_score': round(composite_score, 4)  # 添加综合评分用于调试
            }
            
            model_list.append((model_info, composite_score))
        
        # 按综合评分降序排序（最好的模型在前）
        model_list.sort(key=lambda x: x[1], reverse=True)
        
        # 提取排序后的模型信息（去掉评分）
        sorted_models = [model_info for model_info, _ in model_list]
        
        return JsonResponse({
            'success': True,
            'data': {
                'origin_airport': origin_airport,
                'destination_airport': destination_airport,
                'time_granularity': time_granularity,
                'model_count': len(sorted_models),
                'models': sorted_models
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'error': '服务器内部错误',
            'message': str(e)
        }, status=500)

# 预测并返回结果函数+层级对齐
@api_view(['POST'])
@csrf_exempt
def forecast_route_view(request):
    """
       批量预测航线座位数

       请求体格式：
      {
         "predictions": [
           {
             "hierarchy_reconcile": 1,
             "origin_airport": "CAN",
             "destination_airport": "PEK",
             "time_granularity": "monthly",
             "prediction_periods": 12,
             "monthly_model_id": "CAN_PEK_20250813233020",
             "quarterly_model_id": "CAN_PEK_20250813233015"
           },
           {
             "hierarchy_reconcile": 0,
             "origin_airport": "CAN",
             "destination_airport": "PVG",
             "time_granularity": "monthly",
             "prediction_periods": 12,
             "model_id": "CAN_PVG_20250813233021"
           }
         ]
       }

       返回格式：
       {
           "success": true,
           "data": [
               {
                   "task_index": 0,
                   "hierarchy_reconcile": 0,
                   data{
                       "model_info": {
                           "model_id": "model_id_123",
                           "origin_airport": "CAN",
                           "destination_airport": "PEK",
                           "time_granularity": "monthly",
                           "model_type": "LightGBM",
                           "feature_count": 25,
                           "training_samples": 120,
                           "test_samples": 30,
                           "train_mae": 45.2,
                           "train_rmse": 67.8,
                           "train_mape": 0.15,
                           "train_r2": 0.89,
                           "test_mae": 52.1,
                           "test_rmse": 71.3,
                           "test_mape": 0.18,
                           "test_r2": 0.85,
                           "train_start_time": "2023-01-01",
                           "train_end_time": "2023-12-31",
                           "last_complete_date": "2024-01-31"
                       },
                       "prediction_results": {
                           "historical_data": [
                               {"time_point": "2023-01", "value": 1200},
                               {"time_point": "2023-02", "value": 1350}
                           ],
                           "future_predictions": [
                               {"time_point": "2024-02", "value": 1400},
                               {"time_point": "2024-03", "value": 1450}
                           ]
                           "exit_predictions"：
                       }
                   }
               }
           ]
       }
    """
    try:
        data = json.loads(request.body)
        predictions = data.get('predictions', [])
        print("predictions", predictions)
        if not predictions:
            return JsonResponse({'error': '缺少预测请求', 'message': '请提供 predictions 数组'}, status=400)

        results = []
        # 获得预测时间长度
        target_granularity = predictions[0].get('time_granularity')
        prediction_periods = predictions[0].get('prediction_periods')
        if target_granularity == 'monthly':
            months = prediction_periods
        elif target_granularity == 'quarterly':
            months = prediction_periods * 3
        elif target_granularity == 'yearly':
            months = prediction_periods * 12
        else:
            return JsonResponse({
                'error': '不支持的时间粒度',
                'message': 'time_granularity 必须为 monthly, quarterly 或 yearly'
            }, status=400)

        q_periods = max(1, math.ceil(months / 3))

        for i, pred in enumerate(predictions):
            try:
                hierarchy_reconcile = int(pred.get('hierarchy_reconcile', 0))
                user_max_lr_rate = pred.get('max_lr_rate')
                if user_max_lr_rate is not None:
                    try:
                        user_max_lr_rate = float(user_max_lr_rate)
                        if not (0 <= user_max_lr_rate <= 1.0):
                            return JsonResponse({'error': f'任务 {i}: max_lr_rate 必须为在0-1之间'}, status=400)
                    except ValueError:
                        return JsonResponse({'error': f'任务 {i}: max_lr_rate 必须为数字'}, status=400)

                if hierarchy_reconcile == 0:
                    # === 非对齐预测逻辑 ===
                    required_fields = ['origin_airport', 'destination_airport', 'time_granularity', 'prediction_periods', 'model_id']
                    missing_fields = [field for field in required_fields if field not in pred]
                    if missing_fields:
                        raise ValueError(f'缺少字段: {", ".join(missing_fields)}')

                    if pred['time_granularity'] not in ['yearly', 'quarterly', 'monthly']:
                        raise ValueError('time_granularity 必须是 yearly, quarterly 或 monthly 之一')

                    if not isinstance(pred['prediction_periods'], int) or pred['prediction_periods'] <= 0:
                        raise ValueError('prediction_periods 必须是正整数')

                    result = predict_single_route(pred)
                    result = attach_existing_ask_predictions(result)
                    print(result)
                    results.append({
                        'task_index': i,
                        'hierarchy_reconcile': 0,
                        'data': result
                    })

                else:
                    # === 层级对齐逻辑 ===
                    algo = (pred.get('reconcile_algo') or 'linear').lower()
                    recon_fn = linear_reconcile_monthly_to_quarterly if algo != 'mint' else mint_reconcile_monthly_to_quarterly

                    for f in ['origin_airport', 'destination_airport', 'prediction_periods', 'monthly_model_id', 'quarterly_model_id']:
                        if f not in pred:
                            raise ValueError(f'缺少字段: {f}（hierarchy_reconcile=1 时必填）')

                    if not isinstance(pred['prediction_periods'], int) or pred['prediction_periods'] <= 0:
                        raise ValueError('prediction_periods 必须是正整数')


                    base = {
                        'origin_airport': pred['origin_airport'],
                        'destination_airport': pred['destination_airport'],
                    }

                    monthly_req = {
                        **base,
                        'time_granularity': 'monthly',
                        'prediction_periods': months,
                        'model_id': pred['monthly_model_id'],
                        # 透传经济尾部处理参数（可选）
                        'economic_tail_method': pred.get('economic_tail_method'),
                        'economic_growth_rate': pred.get('economic_growth_rate'),
                        'max_lr_rate': user_max_lr_rate
                    }
                    quarterly_req = {
                        **base,
                        'time_granularity': 'quarterly',
                        'prediction_periods': q_periods,
                        'model_id': pred['quarterly_model_id'],
                        # 透传经济尾部处理参数（可选）
                        'economic_tail_method': pred.get('economic_tail_method'),
                        'economic_growth_rate': pred.get('economic_growth_rate'),
                        'max_lr_rate': user_max_lr_rate
                    }

                    # 1. 执行两套模型预测
                    monthly_resp = predict_single_route(monthly_req)
                    quarterly_resp = predict_single_route(quarterly_req)

                    # 2. 转为DataFrame
                    pm = monthly_resp.get('prediction_results', {})
                    hist_m = pm.get('historical_data', []) or []
                    futu_m = pm.get('future_predictions', []) or []
                    df_m = pd.DataFrame(
                        [{'YearMonth': h['time_point'], 'Predicted': h['value'], 'Set': 'History'} for h in hist_m] +
                        [{'YearMonth': f['time_point'], 'Predicted': f['value'], 'Set': 'Future'} for f in futu_m],
                        columns=['YearMonth', 'Predicted', 'Set']
                    )

                    pq = quarterly_resp.get('prediction_results', {})
                    q_hist = pq.get('historical_data', []) or []
                    q_futu = pq.get('future_predictions', []) or []
                    q_all = q_hist + q_futu
                    df_q = pd.DataFrame(
                        [{'YearMonth': r['time_point'], 'Predicted': r['value']} for r in q_all],
                        columns=['YearMonth', 'Predicted']
                    )

                    # 3. 对齐
                    df_m_rec = recon_fn(df_m, df_q)

                    # 4. 拆分历史和未来（月度）
                    df_m_rec['YearMonth'] = pd.to_datetime(df_m_rec['YearMonth'], errors='coerce', format='%Y-%m')
                    hist_out_m = [
                        {'time_point': t.strftime('%Y-%m'), 'value': int(v) if pd.notna(v) else None}
                        for t, v in zip(
                            df_m_rec.loc[df_m_rec['Set'] == 'History', 'YearMonth'],
                            df_m_rec.loc[df_m_rec['Set'] == 'History', 'Predicted']
                        ) if pd.notna(t)
                    ]
                    futu_out_m = [
                        {'time_point': t.strftime('%Y-%m'), 'value': int(round(v)) if pd.notna(v) else None}
                        for t, v in zip(
                            df_m_rec.loc[df_m_rec['Set'] == 'Future', 'YearMonth'],
                            df_m_rec.loc[df_m_rec['Set'] == 'Future', 'Predicted_Reconciled']
                        ) if pd.notna(t)
                    ]

                    # 5. 年度聚合（基于季度）
                    yearly_hist, yearly_futu = aggregate_quarterly_to_year_by_blocks(q_hist, q_futu)

                    # 6. 构造结构 —— 只返回目标粒度
                    if target_granularity == 'monthly':
                        selected_item = {
                            'model_info': {
                                **(monthly_resp.get('model_info') or {}),
                                'time_granularity': 'monthly',
                                'model_id': pred['monthly_model_id']
                            },
                            'prediction_results': {
                                'historical_data': hist_out_m,
                                'future_predictions': futu_out_m
                            }
                        }

                    elif target_granularity == 'quarterly':
                        selected_item = {
                            'model_info': {
                                **(quarterly_resp.get('model_info') or {}),
                                'time_granularity': 'quarterly',
                                'model_id': pred['quarterly_model_id']
                            },
                            'prediction_results': {
                                'historical_data': q_hist,
                                'future_predictions': q_futu
                            }
                        }

                    elif target_granularity == 'yearly':
                        selected_item = {
                            'model_info': {
                                **(quarterly_resp.get('model_info') or {}),
                                'time_granularity': 'yearly',
                                'model_id': pred['quarterly_model_id']  # 因为年是从季聚合来的
                            },
                            'prediction_results': {
                                'historical_data': yearly_hist,
                                'future_predictions': yearly_futu
                            }
                        }
                    selected_item = attach_existing_ask_predictions(selected_item)
                    print(selected_item)
                    # 添加到最终统一结果中
                    results.append({
                        'task_index': i,
                        'hierarchy_reconcile': 1,
                        'data': selected_item
                    })


            except Exception as e:
                import traceback
                results.append({
                    'task_index': i,
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'request': pred
                })

        return JsonResponse({
            'success': True,
            'data': results
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的JSON格式', 'message': '请求体必须是有效的JSON格式'}, status=400)
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': '服务器内部错误',
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }, status=500)


# 模型训练请求处理
@api_view(['POST'])
@csrf_exempt
def pretrain_model_request(request):
    """
    处理模型训练请求的POST接口
    
    请求体参数：
    - origin: 起始机场代码 (如 'CAN')
    - destination: 目标机场代码 (如 'PEK')
    - config: 训练配置字典，包含：
      - time_granularity: 时间粒度 (yearly/quarterly/monthly)
      - model_type: 模型类型 (lgb/xgb)
      - test_size: 测试集大小
      - add_ts_forecast: 是否添加时间序列预测
      - arima_order: ARIMA参数 (可选)
      - 其他模型特定参数
    
    返回：
    - 成功：训练结果和创建的数据库记录信息
    - 失败：错误信息和失败的数据库记录信息
    """
    try:
        # 获取请求数据
        data = request.data
        
        # 验证必要参数
        origin = data.get('origin', '').upper()
        destination = data.get('destination', '').upper()
        config = data.get('config', {})
        
        if not origin or not destination:
            return Response({
                'error': '缺少必要参数',
                'message': '请提供 origin 和 destination 参数'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not config:
            return Response({
                'error': '缺少配置参数',
                'message': '请提供训练配置 config'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证时间粒度
        time_granularity = config.get('time_granularity', 'monthly')
        if time_granularity not in ['yearly', 'quarterly', 'monthly']:
            return Response({
                'error': '无效的时间粒度',
                'message': 'time_granularity 必须是 yearly, quarterly 或 monthly 之一'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证模型类型
        model_type = config.get('model_type', 'lgb')
        if model_type not in ['lgb', 'xgb']:
            return Response({
                'error': '无效的模型类型',
                'message': 'model_type 必须是 lgb 或 xgb 之一'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        print(f"收到训练请求: {origin} -> {destination}")
        # print(f"配置: {config}")
        
        # 执行模型训练
        success, result = pretrain_single_route(origin, destination, config)
        
        # 准备创建数据库记录的数据
        record_data = {
            'origin': origin,
            'destination': destination,
            'time_granularity': time_granularity,
            'step_size': config.get('test_size'),
            'train_datetime': datetime.now(),
            'success': success,
            'use_pretrain': False
        }
        
        # 如果训练成功，添加成功相关的数据
        if success and isinstance(result, dict):
            record_data.update({
                'meta_file_path': result.get('meta_file_path', ''),
                'train_start_date': result.get('train_start_date'),
                'train_end_date': result.get('train_end_date'),
                'train_duration': result.get('train_duration'),
                'train_mae': result.get('train_mae'),
                'train_rmse': result.get('train_rmse'),
                'train_mape': result.get('train_mape'),
                'train_r2': result.get('train_r2'),
                'test_mae': result.get('test_mae'),
                'test_rmse': result.get('test_rmse'),
                'test_mape': result.get('test_mape'),
                'test_r2': result.get('test_r2'),
                'report_pdf': result.get('report_pdf')
            })
        else:
            # 训练失败，设置默认值
            record_data.update({
                'meta_file_path': '',
                'train_start_date': datetime.now().date(),
                'train_end_date': datetime.now().date(),
                'train_duration': None,
                'train_mae': None,
                'train_rmse': None,
                'train_mape': None,
                'train_r2': None,
                'test_mae': None,
                'test_rmse': None,
                'test_mape': None,
                'test_r2': None,
                'report_pdf': ''
            })
        
        # 清理数据中的nan值
        record_data = clean_nan_values(record_data)
        # print(record_data)
        pretrain_record = PretrainRecord.objects.create(**record_data)
        
        # 构建响应数据
        response_data = {
            'message': '模型训练请求处理完成',
            'record_id': pretrain_record.id,
            'success': True,
            'record_created': True
        }
        
        if success:
            # 清理训练结果数据，确保JSON兼容
            cleaned_result = clean_nan_values(result) if isinstance(result, dict) else result
            response_data.update({
                'training_result': cleaned_result,
                'message': f'航线 {origin}-{destination} 模型训练成功',
                'download_urls': {
                    'report_pdf': cleaned_result.get('report_pdf'),
                    'data_path': cleaned_result.get('data_with_features_path')
                }
            })
        else:
            response_data.update({
                'error': str(result),
                'message': f'航线 {origin}-{destination} 模型训练失败'
            })
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"处理训练请求时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 即使发生异常，也尝试创建失败的记录
        try:
            record_data = {
                'origin': data.get('origin', '').upper() if 'data' in locals() else '',
                'destination': data.get('destination', '').upper() if 'data' in locals() else '',
                'time_granularity': data.get('config', {}).get('time_granularity', 'monthly') if 'data' in locals() else 'monthly',
                'step_size': data.get('config', {}).get('test_size', 12) if 'data' in locals() else 12,
                'train_datetime': datetime.now(),
                'success': False,
                'use_pretrain': False,
                'meta_file_path': '',
                'train_start_date': datetime.now().date(),
                'train_end_date': datetime.now().date(),
                'train_duration': None,
                'train_mae': None,
                'train_rmse': None,
                'train_mape': None,
                'train_r2': None,
                'test_mae': None,
                'test_rmse': None,
                'test_mape': None,
                'test_r2': None,
                'report_pdf': ''
            }

            # 清理数据中的nan值
            record_data = clean_nan_values(record_data)
            pretrain_record = PretrainRecord.objects.create(**record_data)
            
            return Response({
                'error': '系统异常',
                'message': f'处理训练请求时发生系统异常: {str(e)}',
                'record_id': pretrain_record.id,
                'record_created': True,
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        except Exception as record_error:
            print(f"创建失败记录时也发生错误: {str(record_error)}")
            return Response({
                'error': '系统异常',
                'message': f'处理训练请求时发生系统异常: {str(e)}，且无法创建失败记录',
                'record_created': False,
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['POST'])
@csrf_exempt
def formal_train_model(request):
    """
    正式训练模型接口
    
    请求参数：
    - pretrain_record_id: 预训练模型记录ID
    - remark: 备注信息（可选）
    
    流程：
    1. 根据预训练模型ID查找PretrainRecord
    2. 提取origin, destination, meta_file_path, time_granularity和8个指标参数
    3. 调用formal_train_single_route函数进行训练
    4. 成功时创建RouteModelInfo记录并更新PretrainRecord的use_pretrain为True
    5. 失败时返回错误信息，不修改数据库
    """
    try:
        # 获取请求参数
        pretrain_record_id = request.data.get('pretrain_record_id')
        remark = request.data.get('remark', '')  # 备注可以为空
        
        # 参数验证
        if not pretrain_record_id:
            return Response({
                'error': '缺少必要参数',
                'message': '请提供 pretrain_record_id 参数'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 查找预训练记录
        try:
            pretrain_record = PretrainRecord.objects.get(id=pretrain_record_id)
        except PretrainRecord.DoesNotExist:
            return Response({
                'error': '预训练记录不存在',
                'message': f'ID为 {pretrain_record_id} 的预训练记录不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 检查预训练记录是否成功
        if not pretrain_record.success:
            return Response({
                'error': '预训练记录状态异常',
                'message': f'预训练记录 {pretrain_record_id} 训练状态为失败，无法用于正式训练'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 提取预训练记录中的参数
        origin = pretrain_record.origin
        destination = pretrain_record.destination
        meta_file_path = pretrain_record.meta_file_path
        time_granularity = pretrain_record.time_granularity
        
        # 提取8个评估指标
        train_metrics = {
            'train_mae': pretrain_record.train_mae,
            'train_rmse': pretrain_record.train_rmse,
            'train_mape': pretrain_record.train_mape,
            'train_r2': pretrain_record.train_r2,
            'test_mae': pretrain_record.test_mae,
            'test_rmse': pretrain_record.test_rmse,
            'test_mape': pretrain_record.test_mape,
            'test_r2': pretrain_record.test_r2,
        }
        
        print(f"开始正式训练模型: {origin}-{destination}, 时间粒度: {time_granularity}")
        # print(f"使用预训练元数据: {meta_file_path}")
        
        success, result = formal_train_single_route(
            origin=origin,
            destination=destination,
            time_granularity=time_granularity,
            pretrained_metadata_path=meta_file_path
        )
        
        if success:
            # 训练成功，创建RouteModelInfo记录
            try:
                # 创建RouteModelInfo记录
                model_id = result["model_id"]
                
                # 准备创建记录的数据
                route_model_data = {
                    'model_id': model_id,
                    'origin_airport': origin,
                    'destination_airport': destination,
                    'time_granularity': time_granularity,
                    'train_start_time': result['train_start_time'],
                    'train_end_time': result['train_end_time'],
                    'train_datetime': result['train_datetime'],
                    'meta_file_path': result['meta_file_path'],
                    'model_file_path': result['model_file_path'],
                    'raw_data_file_path': result['raw_data_file_path'],
                    'preprocessor_file_path': result['preprocessor_file_path'],
                    'feature_builder_file_path': result['feature_builder_file_path'],
                    # 8个评估指标
                    'train_mae': train_metrics['train_mae'],
                    'train_rmse': train_metrics['train_rmse'],
                    'train_mape': train_metrics['train_mape'],
                    'train_r2': train_metrics['train_r2'],
                    'test_mae': train_metrics['test_mae'],
                    'test_rmse': train_metrics['test_rmse'],
                    'test_mape': train_metrics['test_mape'],
                    'test_r2': train_metrics['test_r2'],
                    'remark': remark,
                    'pretrain_record': pretrain_record
                }
                
                # 清理数据中的nan值
                route_model_data = clean_nan_values(route_model_data)
                
                route_model_info = RouteModelInfo.objects.create(**route_model_data)
                
                # 更新PretrainRecord的use_pretrain为True
                pretrain_record.use_pretrain = True
                pretrain_record.save()
                
                # print(f"正式训练成功！创建RouteModelInfo记录: {model_id}")
                
                return Response({
                    'success': True,
                    'message': f'航线 {origin}-{destination} 正式训练成功',
                    'model_id': model_id,
                    'route_model_info_id': route_model_info.model_id,
                    'pretrain_record_updated': True
                }, status=status.HTTP_200_OK)
                
            except Exception as create_error:
                print(f"创建RouteModelInfo记录时发生错误: {str(create_error)}")
                import traceback
                traceback.print_exc()
                
                return Response({
                    'error': '数据库操作失败',
                    'message': f'模型训练成功，但创建数据库记录失败: {str(create_error)}',
                    'training_success': True,
                    'database_operation_failed': True
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        else:
            # 训练失败
            print(f"正式训练失败: {result}")
            
            return Response({
                'error': '模型训练失败',
                'message': f'航线 {origin}-{destination} 正式训练失败: {result}',
                'training_success': False
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"处理正式训练请求时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response({
            'error': '系统异常',
            'message': f'处理正式训练请求时发生系统异常: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
def get_pretrain_models(request):
    """
    获取预训练成功的模型列表
    
    参数：
    - origin_airport: 起点机场三字码（可选）
    - destination_airport: 终点机场三字码（可选）
    - time_granularity: 时间粒度 (yearly/quarterly/monthly)（可选）
    
    返回：
    - 预训练成功的模型列表，每个模型包含：
      - 基本信息：ID、起终点、时间粒度、训练时间等
      - 训练结果指标：训练集和测试集的评估指标
      - 是否被采用为正式模型
    """
    try:
        # 获取查询参数
        origin_airport = request.GET.get('origin_airport', '').upper()
        destination_airport = request.GET.get('destination_airport', '').upper()
        time_granularity = request.GET.get('time_granularity', '')
        
        # 构建查询条件
        query_filters = {'success': True}  # 只要预训练成功的模型
        
        if origin_airport:
            query_filters['origin'] = origin_airport
            
        if destination_airport:
            query_filters['destination'] = destination_airport
            
        if time_granularity:
            if time_granularity not in ['yearly', 'quarterly', 'monthly']:
                return JsonResponse({
                    'error': '无效的时间粒度',
                    'message': 'time_granularity 必须是 yearly, quarterly 或 monthly 之一'
                }, status=400)
            query_filters['time_granularity'] = time_granularity
        
        # 查询预训练成功的模型
        pretrain_models = PretrainRecord.objects.filter(**query_filters).order_by('-train_datetime')
        
        if not pretrain_models.exists():
            return JsonResponse({
                'message': '未找到符合条件的预训练模型',
                'models': [],
                'count': 0
            }, status=200)
        
        # 构建返回数据
        models_data = []
        for model in pretrain_models:
            model_info = {
                # 基本信息
                'id': model.id,
                'origin': model.origin,
                'destination': model.destination,
                'time_granularity': model.time_granularity,
                'train_start_date': model.train_start_date.strftime('%Y-%m-%d') if model.train_start_date else None,
                'train_end_date': model.train_end_date.strftime('%Y-%m-%d') if model.train_end_date else None,
                'train_datetime': model.train_datetime.strftime('%Y-%m-%d %H:%M:%S') if model.train_datetime else None,
                'train_duration': str(model.train_duration) if model.train_duration else None,
                'report_pdf': model.report_pdf,
                'created_at': model.created_at.strftime('%Y-%m-%d %H:%M:%S') if model.created_at else None,
                
                # 训练结果指标
                'train_metrics': {
                    'mae': model.train_mae,
                    'rmse': model.train_rmse,
                    'mape': model.train_mape,
                    'r2': model.train_r2
                },
                'test_metrics': {
                    'mae': model.test_mae,
                    'rmse': model.test_rmse,
                    'mape': model.test_mape,
                    'r2': model.test_r2
                },
                
                # 是否被采用为正式模型
                'is_adopted': model.use_pretrain,
                
                # 模型状态
                'success': model.success
            }
            
            models_data.append(model_info)
        
        return JsonResponse({
            'success': True,
            'message': f'成功获取 {len(models_data)} 个预训练模型',
            'models': models_data,
            'count': len(models_data),
            'filters_applied': {
                'origin_airport': origin_airport if origin_airport else None,
                'destination_airport': destination_airport if destination_airport else None,
                'time_granularity': time_granularity if time_granularity else None
            }
        }, status=200)
        
    except Exception as e:
        print(f"获取预训练模型列表时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'error': '系统异常',
            'message': f'获取预训练模型列表时发生系统异常: {str(e)}'
        }, status=500)


@api_view(['GET'])
def query_flight_market(request):
    """
    查询航线市场数据（直接查表，不做聚合，返回前1000条，按 year_month 升序）

    参数（可选，未传则全选）:
    - origin: 起点机场三字码，支持逗号分隔
    - destination: 终点机场三字码，支持逗号分隔
    - start_date: 开始日期 (YYYY-MM 或 YYYY-MM-DD)
    - end_date: 结束日期 (YYYY-MM 或 YYYY-MM-DD)
    """
    try:
        qs = FlightMarketRecord.objects.all()

        # 参数
        origin = request.GET.get("origin")
        destination = request.GET.get("destination")
        start_date = request.GET.get("start_date")
        end_date = request.GET.get("end_date")

        if origin:
            qs = qs.filter(origin__in=[x.strip().upper() for x in origin.split(",") if x.strip()])
        if destination:
            qs = qs.filter(destination__in=[x.strip().upper() for x in destination.split(",") if x.strip()])

        start_month = _to_year_month(start_date)
        end_month = _to_year_month(end_date)
        if start_month and end_month:
            qs = qs.filter(year_month__gte=start_month, year_month__lte=end_month)
        elif start_month:
            qs = qs.filter(year_month__gte=start_month)
        elif end_month:
            qs = qs.filter(year_month__lte=end_month)

        # 排序 + 限制
        records = qs.values(
            "year_month",
            "origin", "destination",
            "distance_km",
            "route_total_flights", "route_total_seats",
            "route_total_flight_time", "route_avg_flight_time",
            "con_total_est_pax", "first", "business", "premium",
            "full_y", "disc_y",
            "avg_yield", "avg_first", "avg_business", "avg_premium",
            "avg_full_y", "avg_disc_y",
            "region",
            "total_est_pax", "local_est_pax", "behind_est_pax",
            "bridge_est_pax", "beyond_est_pax",
            "avg_fare_usd", "local_fare", "behind_fare",
            "bridge_fare", "beyond_fare",
            "o_gdp", "o_population", "third_industry_x",
            "o_revenue", "o_retail", "o_labor", "o_air_traffic",
            "d_gdp", "d_population", "third_industry_y",
            "d_revenue", "d_retail", "d_labor", "d_air_traffic",
        ).distinct().order_by("year_month")[:1000]

        # 转换 origin / destination 三字码 -> 机场信息
        data = []
        for r in records:
            r = dict(r)  # values() 返回的是 dict-like
            r["origin"] = build_info(r["origin"])
            r["destination"] = build_info(r["destination"])
            data.append(r)

        return JsonResponse({
            "success": True,
            "count": len(data),
            "data": data
        }, status=200)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            "success": False,
            "error": "系统异常",
            "message": str(e)
        }, status=500)


@api_view(['POST'])
@csrf_exempt
def download_train_file(request):
    """
    下载文件接口

    参数：
    - file_path: 文件相对路径（相对于Pre_trained_Models目录）
    - file_type: 文件类型 (report_pdf 或 data_with_features)

    返回：
    - 文件下载
    """
    print(f"下载接口被调用: {request.method}")
    print(f"请求数据: {request.data}")
    try:
        # 获取参数，支持GET和POST请求
        if request.method == 'GET':
            file_path = request.GET.get('file_path')
            file_type = request.GET.get('file_type', '')
        else:  # POST请求
            file_path = request.data.get('file_path')
            file_type = request.data.get('file_type', '')

        if not file_path:
            return JsonResponse({
                'error': '缺少必要参数',
                'message': '请提供 file_path 参数'
            }, status=400)

        # 处理文件路径：将URL编码的反斜杠转换为正斜杠，然后转换为系统路径分隔符
        # 首先解码URL编码
        import urllib.parse
        decoded_path = urllib.parse.unquote(file_path)
        # 将正斜杠转换为系统路径分隔符
        normalized_path = os.path.normpath(decoded_path.replace('/', os.sep))

        # 构建完整文件路径
        current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/predict/
        model_dir = os.path.join(os.path.dirname(current_dir), 'AirlineModels')  # backend/AirlineModels

        # 预训练模型目录和已存在模型目录
        pre_trained_model_dir = os.path.join(model_dir, 'Pre_trained_Models')

        # 根据文件类型选择正确的目录
        if file_type == 'data_with_features':
            # 特征数据文件只在预训练目录
            full_file_path = os.path.join(pre_trained_model_dir, normalized_path)
        elif file_type == 'report_pdf':
            full_file_path = os.path.join(pre_trained_model_dir, normalized_path)

        # 检查文件是否存在
        print(f"完整文件路径: {full_file_path}")
        print(f"文件是否存在: {os.path.exists(full_file_path)}")
        if not os.path.exists(full_file_path):
            return JsonResponse({
                'error': '文件不存在',
                'message': f'文件不存在: {file_path}',
                'full_path': full_file_path
            }, status=404)

        # 根据文件类型设置文件名和内容类型
        if file_type == 'report_pdf':
            filename = os.path.basename(file_path)
            content_type = 'application/pdf'
        elif file_type == 'data_with_features':
            # 从路径中提取航线信息
            path_parts = file_path.split(os.sep)
            if len(path_parts) >= 3:
                route_info = path_parts[-2]  # 例如: CAN_PEK_20250101120000
                filename = f"{route_info}_features.csv"
            else:
                filename = "features_data.csv"
            content_type = 'text/csv'
        else:
            filename = os.path.basename(file_path)
            content_type = 'application/octet-stream'

        # 返回文件下载响应
        try:
            print(f"准备下载文件: {filename}")
            print(f"文件大小: {os.path.getsize(full_file_path)} bytes")

            file_handle = open(full_file_path, 'rb')
            response = FileResponse(
                file_handle,
                as_attachment=True,
                filename=filename,
                content_type=content_type
            )
            # 设置响应头
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            print(f"文件响应已创建，准备返回")
            return response
        except Exception as file_error:
            print(f"打开文件时发生错误: {str(file_error)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'error': '文件读取失败',
                'message': f'无法读取文件: {str(file_error)}'
            }, status=500)

    except Exception as e:
        print(f"下载文件时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

        return JsonResponse({
            'error': '系统异常',
            'message': f'下载文件时发生系统异常: {str(e)}'
        }, status=500)


import decimal
from django.db import transaction
from .predictive_algorithm.utils_flight_import import parse_upload_file_for_preview, parse_csv_content


def _to_decimal_or_none(v):
    if v in (None, "", "null"):
        return None
    try:
        return decimal.Decimal(str(v))
    except Exception:
        return None

@csrf_exempt
@require_POST
def flight_market_upload_preview(request):
    """
    步骤1：上传文件
    - 非冲突行：直接写库（新建）
    - 冲突行：返回给前端，让用户选覆盖/跳过
    """
    upload_file = request.FILES.get("file")
    if not upload_file:
        return JsonResponse({"code": 400, "msg": "缺少文件(file)"}, status=400)

    try:
        all_rows = parse_upload_file_for_preview(upload_file)
    except Exception as e:
        return JsonResponse({"code": 500, "msg": f"解析失败: {e}"}, status=500)

    conflict_rows = []
    auto_created = 0

    with transaction.atomic():
        model_field_names = {f.name for f in FlightMarketRecord._meta.concrete_fields}
        for row in all_rows:
            data = row["data"]
            ym = data.get("year_month")
            origin = data.get("origin")
            dest = data.get("destination")

            if not row["has_conflict"]:
                # 直接新建写库
                obj = FlightMarketRecord()
                # 系统管理的字段，不参与设置
                excluded_fields = {"id", "created_at", "updated_at"}
                for field_name, value in data.items():
                    # 跳过系统管理的字段
                    if field_name in excluded_fields:
                        continue
                    if field_name not in model_field_names:
                        continue
                    
                    if field_name in ("year_month", "origin", "destination", "equipment", "region"):
                        setattr(obj, field_name, value)
                    elif field_name == "international_flight":
                        if isinstance(value, bool):
                            setattr(obj, field_name, value)
                        else:
                            setattr(obj, field_name, str(value).lower() == "true")
                    else:
                        setattr(obj, field_name, _to_decimal_or_none(value))
                obj.save()
                auto_created += 1
            else:
                # 冲突行先不动，丢到列表里返回前端
                conflict_rows.append(row)

    return JsonResponse({
        "code": 0,
        "msg": "ok",
        "data": {
            "auto_created": auto_created,   # 已直接导入多少条
            "conflict_rows": conflict_rows  # 需要人工处理的冲突行
        }
    })

@csrf_exempt
@require_POST
def flight_market_upload_commit(request):
    """
    步骤2：前端提交“冲突行 + action”
    body: {
      "rows": [
        {
          "action": "overwrite" | "skip",
          "data": {...}
        }, ...
      ]
    }
    """
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"code": 400, "msg": "请求体必须是 JSON"}, status=400)

    rows = body.get("rows") or []
    if not isinstance(rows, list):
        return JsonResponse({"code": 400, "msg": "rows 必须是数组"}, status=400)

    updated = 0
    skipped = 0
    objects_to_update = []
    objects_to_create = []
    now = timezone.now()

    with transaction.atomic():
        model_field_names = {f.name for f in FlightMarketRecord._meta.concrete_fields}
        for row in rows:
            action = row.get("action", "skip")
            data = row.get("data") or {}
            ym = data.get("year_month")
            origin = data.get("origin")
            dest = data.get("destination")

            if action == "skip":
                skipped += 1
                continue

            # 理论上必然存在，因为这是"冲突行"
            obj = FlightMarketRecord.objects.filter(
                year_month=ym,
                origin=origin,
                destination=dest,
            ).first()
            
            excluded_fields = {"id", "created_at", "updated_at"}
            
            if not obj:
                # 极端情况：中间被删了，那就当新建
                obj = FlightMarketRecord()
                is_new = True
            else:
                # 如果存在，保留 id 和 created_at
                # updated_at 需要手动设置为当前时间（因为 bulk_update 不会自动更新 auto_now 字段）
                is_new = False

            # 覆盖所有字段（排除 id, created_at, updated_at，这些字段由系统管理）
            for field_name, value in data.items():
                # 跳过系统管理的字段
                if field_name in excluded_fields:
                    continue

                # qty增加下面
                if field_name not in model_field_names:
                    continue
                # 关键逻辑：如果这一列在 CSV 里是空的，就不覆盖原值
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    continue
                    
                if field_name in ("year_month", "origin", "destination", "equipment", "region"):
                    setattr(obj, field_name, value)
                elif field_name == "international_flight":
                    if isinstance(value, bool):
                        setattr(obj, field_name, value)
                    else:
                        setattr(obj, field_name, str(value).lower() == "true")
                else:
                    setattr(obj, field_name, _to_decimal_or_none(value))
            
            # 对于更新操作，手动设置 updated_at
            if not is_new:
                obj.updated_at = now
                objects_to_update.append(obj)
            else:
                objects_to_create.append(obj)
        
        # 批量创建新记录
        if objects_to_create:
            FlightMarketRecord.objects.bulk_create(objects_to_create)
            updated += len(objects_to_create)
        
        # 批量更新现有记录
        if objects_to_update:
            # 获取所有需要更新的字段名（排除系统管理字段）
            update_fields = [f.name for f in FlightMarketRecord._meta.get_fields() 
                           if f.name not in {'id', 'created_at', 'updated_at'} 
                           and not (f.many_to_many or f.one_to_many or f.many_to_one)]
            # 确保 updated_at 在更新字段列表中
            if 'updated_at' not in update_fields:
                update_fields.append('updated_at')
            
            FlightMarketRecord.objects.bulk_update(objects_to_update, update_fields)
            updated += len(objects_to_update)

    return JsonResponse({
        "code": 0,
        "msg": "冲突处理完成",
        "data": {
            "updated": updated,
            "skipped": skipped,
        }
    })


# 前端上传接口（适配前端 CSV 文本格式，同时支持上传 Excel 文件）
@api_view(['POST'])
@csrf_exempt
def upload_check(request):
    """
    检查上传数据，返回冲突信息
    请求体:
    - JSON: { "content": "CSV文本内容" }
    - multipart/form-data: file=上传的 csv/xlsx/xls
    返回:
    - status: 1=无冲突可上传, 2=有冲突需处理, 3=格式错误
    - conflicts: 冲突列表（status=2时）
    """
    try:
        upload_file = request.FILES.get('file')
        if upload_file:
            # 解析上传的 CSV/Excel 文件
            try:
                all_rows = parse_csv_content(file_obj=upload_file)
            except ValueError as e:
                import traceback
                traceback.print_exc()
                print(f"解析发生严重错误: {e}")
                return JsonResponse({
                    'status': 3,
                    'message': str(e)
                }, status=400)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"解析发生严重错误: {e}")
                return JsonResponse({
                    'status': 3,
                    'message': f'解析失败: {str(e)}'
                }, status=400)
        else:
            data = json.loads(request.body)
            csv_content = data.get('content', '')
            
            if not csv_content:
                return JsonResponse({
                    'status': 3,
                    'message': '缺少 CSV/Excel 内容'
                }, status=400)
            
            # 解析 CSV 文本
            try:
                all_rows = parse_csv_content(csv_content=csv_content)
            except ValueError as e:
                return JsonResponse({
                    'status': 3,
                    'message': str(e)
                }, status=400)
            except Exception as e:
                return JsonResponse({
                    'status': 3,
                    'message': f'解析失败: {str(e)}'
                }, status=400)

        if not all_rows:
            print("12345")
            return JsonResponse({
                'status': 3,
                'message': '文件为空或格式不正确'
            }, status=400)
        
        # 检查冲突
        conflicts = []
        print(123)
        for row in all_rows:
            if row['has_conflict']:
                conflicts.append({
                    'key': row['key'],
                    'old': row.get('old_data', {}),
                    'new': row['data']
                })
        
        if conflicts:
            return JsonResponse({
                'status': 2,
                'conflicts': conflicts
            })
        else:
            return JsonResponse({
                'status': 1,
                'message': '数据检查通过，无冲突'
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 3,
            'message': '请求体必须是有效的 JSON 格式'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'status': 3,
            'message': f'服务器错误: {str(e)}'
        }, status=500)


@api_view(['POST'])
@csrf_exempt
def upload_insert(request):
    """
    直接插入数据（无冲突时使用）
    请求体:
    - JSON: { "content": "CSV文本内容" }
    - multipart/form-data: file=上传的 csv/xlsx/xls
    返回: { "success": true/false }
    """
    try:
        upload_file = request.FILES.get('file')
        if upload_file:
            # 解析上传的 CSV/Excel 文件
            try:
                all_rows = parse_csv_content(file_obj=upload_file)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'解析失败: {str(e)}'
                }, status=400)
        else:
            data = json.loads(request.body)
            csv_content = data.get('content', '')

            if not csv_content:
                return JsonResponse({
                    'success': False,
                    'message': '缺少 CSV/Excel 内容'
                }, status=400)

            # 解析 CSV 文本
            try:
                all_rows = parse_csv_content(csv_content=csv_content)
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'解析失败: {str(e)}'
                }, status=400)

        if not all_rows:
            return JsonResponse({
                'success': False,
                'message': '文件为空或格式不正确'
            }, status=400)

        # 检查是否有冲突（不应该有，但为了安全还是检查）
        conflict_count = sum(1 for row in all_rows if row['has_conflict'])
        if conflict_count > 0:
            return JsonResponse({
                'success': False,
                'message': f'检测到 {conflict_count} 条冲突数据，请先处理冲突'
            }, status=400)

        # 插入数据
        created_count = 0
        with transaction.atomic():
            model_field_names = {f.name for f in FlightMarketRecord._meta.concrete_fields}
            for row in all_rows:
                data = row['data']
                ym = data.get('year_month', '').strip()
                origin = data.get('origin', '').strip().upper()
                dest = data.get('destination', '').strip().upper()
                equipment = data.get('equipment', '').strip()

                if not ym or not origin or not dest:
                    continue

                # 创建新记录
                obj = FlightMarketRecord()
                # 系统管理的字段，不参与设置
                excluded_fields = {'id', 'created_at', 'updated_at'}
                for field_name, value in data.items():
                    # 跳过系统管理的字段
                    if field_name in excluded_fields:
                        continue
                    if field_name not in model_field_names:
                        continue
                    if field_name in ('year_month', 'origin', 'destination', 'equipment', 'region'):
                        setattr(obj, field_name, value)
                    elif field_name == 'international_flight':
                        if isinstance(value, bool):
                            setattr(obj, field_name, value)
                        else:
                            setattr(obj, field_name, str(value).lower() in ('true', '1', 'y', 'yes'))
                    else:
                        setattr(obj, field_name, _to_decimal_or_none(value))

                try:
                    obj.save()
                    created_count += 1
                except Exception as e:
                    # 忽略唯一约束冲突（可能并发插入）
                    continue

        return JsonResponse({
            'success': True,
            'message': f'成功插入 {created_count} 条数据'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '请求体必须是有效的 JSON 格式'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }, status=500)


@api_view(['POST'])
@csrf_exempt
def upload_resolve(request):
    """
    处理冲突数据
    请求体:
    - JSON: { "decisions": [{"key": "...", "action": "keep"/"replace"}, ...], "content": "CSV文本内容" }
    - multipart/form-data: file=上传的 csv/xlsx/xls, decisions=JSON 字符串, content 可选
    注意：前端需要同时发送完整的 CSV/Excel 数据，以便获取新数据
    返回: { "success": true/false }
    """
    try:
        upload_file = request.FILES.get('file')
        if upload_file:
            decisions_raw = request.POST.get('decisions', '')
            csv_content = request.POST.get('content', '')
            if decisions_raw:
                try:
                    decisions = json.loads(decisions_raw)
                except json.JSONDecodeError:
                    return JsonResponse({
                        'success': False,
                        'message': 'decisions 需要是有效的 JSON 格式'
                    }, status=400)
            else:
                decisions = []
        else:
            data = json.loads(request.body)
            decisions = data.get('decisions', [])
            csv_content = data.get('content', '')  # 需要 CSV/Excel 内容来获取新数据
        
        if not decisions:
            return JsonResponse({
                'success': False,
                'message': '缺少处理决策'
            }, status=400)
        
        if not upload_file and not csv_content:
            return JsonResponse({
                'success': False,
                'message': '缺少 CSV/Excel 内容'
            }, status=400)
        
        # 解析 CSV/Excel 获取新数据
        try:
            all_rows = parse_csv_content(
                csv_content=csv_content if not upload_file else None,
                file_obj=upload_file
            )
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'解析失败: {str(e)}'
            }, status=400)
        
        # 构建 key -> data 映射
        data_map = {row['key']: row['data'] for row in all_rows}
        
        # 处理冲突（批量操作）
        updated_count = 0
        skipped_count = 0
        objects_to_update = []
        objects_to_create = []
        now = timezone.now()
        
        with transaction.atomic():
            model_field_names = {f.name for f in FlightMarketRecord._meta.concrete_fields}
            for decision in decisions:
                key = decision.get('key', '')
                action = decision.get('action', 'keep')
                
                if action == 'keep':
                    skipped_count += 1
                    continue
                
                # action == 'replace'
                new_data = data_map.get(key)
                if not new_data:
                    continue
                
                # 从数据中获取关键字段
                ym = (new_data.get('year_month') or '').strip()
                origin = (new_data.get('origin') or '').strip().upper()
                dest = (new_data.get('destination') or '').strip().upper()
                
                if not ym or not origin or not dest:
                    continue
                
                # 查找现有记录
                obj = FlightMarketRecord.objects.filter(
                    year_month=ym,
                    origin=origin,
                    destination=dest,
                ).first()
                
                excluded_fields = {'id', 'created_at', 'updated_at'}
                
                if not obj:
                    # 如果不存在，创建新记录
                    obj = FlightMarketRecord()
                    is_new = True
                else:
                    # 如果存在，保留 id 和 created_at
                    # updated_at 需要手动设置为当前时间（因为 bulk_update 不会自动更新 auto_now 字段）
                    is_new = False
                
                # 更新所有字段（排除 id, created_at, updated_at，这些字段由系统管理）
                for field_name, value in new_data.items():
                    # 跳过系统管理的字段
                    if field_name in excluded_fields:
                        continue
                    # qty增加下面
                    if field_name not in model_field_names:
                        continue
                    # 空值不更新，保留原来的
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        continue
                    if field_name in ('year_month', 'origin', 'destination', 'equipment', 'region'):
                        setattr(obj, field_name, value)
                    elif field_name == 'international_flight':
                        if isinstance(value, bool):
                            setattr(obj, field_name, value)
                        else:
                            setattr(obj, field_name, str(value).lower() in ('true', '1', 'y', 'yes'))
                    else:
                        setattr(obj, field_name, _to_decimal_or_none(value))
                
                # 对于更新操作，手动设置 updated_at
                if not is_new:
                    obj.updated_at = now
                    objects_to_update.append(obj)
                else:
                    objects_to_create.append(obj)
            
            # 批量创建新记录
            if objects_to_create:
                FlightMarketRecord.objects.bulk_create(objects_to_create)
                updated_count += len(objects_to_create)
            
            # 批量更新现有记录
            if objects_to_update:
                # 获取所有需要更新的字段名（排除系统管理字段）
                update_fields = [f.name for f in FlightMarketRecord._meta.get_fields() 
                               if f.name not in {'id', 'created_at', 'updated_at'} 
                               and not (f.many_to_many or f.one_to_many or f.many_to_one)]
                # 确保 updated_at 在更新字段列表中
                if 'updated_at' not in update_fields:
                    update_fields.append('updated_at')
                
                FlightMarketRecord.objects.bulk_update(objects_to_update, update_fields)
                updated_count += len(objects_to_update)
        
        return JsonResponse({
            'success': True,
            'message': f'处理完成：更新 {updated_count} 条，跳过 {skipped_count} 条'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': '请求体必须是有效的 JSON 格式'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }, status=500)


@api_view(['POST'])
@csrf_exempt
def trigger_update_forecast(request):
    """
    触发预测更新接口
    逻辑：
    1. 检查是否有正在运行的任务。
    2. 如果有，且未超时 -> 返回“正在更新，请等待”。
    3. 如果无，或已超时/失败 -> 创建新任务 -> 返回“开始更新” + “上次成功时间”。
    """

    # 设定超时阈值：例如 48 小时
    # 如果一个任务跑了 48 小时还没结束，我们认为它已经死锁了
    TIMEOUT_HOURS = 48

    last_task = ForecastUpdateLog.objects.first()

    # --- 1. 判断是否“拒绝更新” ---
    can_update = True
    reject_reason = ""

    if last_task:
        # 如果是 Pending 或 Running
        if last_task.status in [0, 1]:
            # 检查是否超时 (防止死锁)
            time_since_start = timezone.now() - last_task.created_at
            if time_since_start.total_seconds() < TIMEOUT_HOURS * 3600:
                # 确实正在跑，且没超时
                can_update = False
                reject_reason = "任务正在进行中"
            else:
                # 超时了，视为死锁，允许覆盖更新（虽然它状态是1，但我们不管它了）
                # 可选：顺手把它标记为失败，保持数据整洁
                last_task.status = 3
                last_task.log_message = "系统检测到超时死锁，强制标记为失败"
                last_task.save()
                can_update = True

    # --- 2. 获取“上一次成功的时间”用于展示 ---
    # 查找最近一条 status=2 的记录
    last_success_task = ForecastUpdateLog.objects.filter(status=2).first()
    last_success_str = "无历史记录"
    if last_success_task and last_success_task.end_time:
        # 格式化时间，例如 "2023-10-27 14:30"
        last_success_str = last_success_task.end_time.strftime("%Y-%m-%d %H:%M")

    # --- 3. 执行逻辑分支 ---

    # 分支 A: 不可更新 (正在跑)
    if not can_update:
        return JsonResponse({
            'code': 400,
            'status': 'running',
            'message': '系统正在进行预测更新，请耐心等待。',
            'data': {
                'start_time': last_task.created_at.strftime("%Y-%m-%d %H:%M")
            }
        })

    # 分支 B: 可以更新 (闲置/失败/死锁复活)
    else:
        # 创建新任务
        ForecastUpdateLog.objects.create(status=0)

        return JsonResponse({
            'code': 200,
            'status': 'started',
            'message': '更新请求已提交，系统开始计算。',
            'data': {
                'estimated_time': '约24小时',
                'last_success_date': last_success_str,
                'note': '在此期间，系统将展示上一次成功的预测数据。'
            }
        })



@api_view(['POST'])
@csrf_exempt
def update_forecast_ask_view(request):
    """
    批量更新（或创建）预测表中的 ask 值。

    请求体：
    {
    "granularity": "quarterly",
    "data": [
        {
            "Origin": "CTU",
            "Destination": "SHA",
            "Time_point": "2024-Q2",
            "Value": 519284316.51573217
        },
        {
            "Origin": "CTU",
            "Destination": "SHA",
            "Time_point": "2024-Q3",
            "Value": 623316619.0815556
        }
    ]
}
    """
    # 1. 解析 JSON
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "无效的 JSON 格式"},
            status=400,
        )

    gran = body.get("granularity")
    results = body.get("data") or []

    # 2. 校验粒度
    if gran not in ("monthly", "quarterly", "yearly"):
        return JsonResponse(
            {"success": False, "error": "time_granularity 必须为 monthly/quarterly/yearly"},
            status=400,
        )

    # 3. 校验结果列表
    if not isinstance(results, list) or not results:
        return JsonResponse(
            {"success": False, "error": "results 必须是非空数组"},
            status=400,
        )

    # 4. 选择对应的模型
    model_map = {
        "monthly": ForecastMonthly,
        "quarterly": ForecastQuarterly,
        "yearly": ForecastYearly,
    }
    ModelCls = model_map[gran]

    parsed_items = []
    errors = []

    # 5. 逐条解析 & 基础校验
    for idx, row in enumerate(results):
        try:
            origin = row.get("Origin")
            destination = row.get("Destination")
            fd_str = row.get("Time_point")
            ask_val = row.get("Value")

            if not origin or not destination:
                raise ValueError("origin/destination 不能为空")
            if not fd_str:
                raise ValueError("Time_point 不能为空")
            if ask_val is None:
                raise ValueError("Value 不能为空")

            # 使用缓和解析逻辑
            forecast_date = parse_forecast_date(gran, fd_str)
            ask_float = float(ask_val)

            parsed_items.append(
                (origin, destination, forecast_date, ask_float)
            )
        except Exception as e:
            errors.append(
                {
                    "index": idx,
                    "row": row,
                    "error": str(e),
                }
            )

    if not parsed_items:
        return JsonResponse(
            {
                "success": False,
                "error": "没有可用的更新项",
                "detail_errors": errors,
            },
            status=400,
        )

    # 6. 批量 update_or_create
    updated = 0
    created = 0
    with transaction.atomic():
        for origin, dest, fdate, ask_val in parsed_items:
            obj, is_created = ModelCls.objects.update_or_create(
                origin=origin,
                destination=dest,
                forecast_date=fdate,
                defaults={"ask": ask_val},
            )
            if is_created:
                created += 1
            else:
                updated += 1

    # 7. 返回结果
    return JsonResponse(
        {
            "success": True,
            "data": {
                "time_granularity": gran,
                "updated": updated,
                "created": created,
                "errors": errors,  # 哪些行失败了会放这里
            },
        }
    )


import csv
import os
from django.conf import settings

ROUTE_RANKING_CSV = os.path.join(
    settings.BASE_DIR, "Predict_Datas", "route_panel_ranking.csv"
)


def get_routes_from_csv(panel_type: str):
    """
    从 route_ranking.csv 里按行号取对应类型的航线列表。

    约定：
      - 文件已经按你需要的规则排好序
      - large:   第 1  ~ 100 行
      - medium:  第 101 ~ 500 行
      - small:   先不处理，返回 []

    csv 头里假定有字段：
      - origin
      - destination
    """
    routes = []
    # print("11111")
    if not os.path.exists(ROUTE_RANKING_CSV):
        print("CSV not exists:", ROUTE_RANKING_CSV)
        return routes

    with open(ROUTE_RANKING_CSV, newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)
        # print("CSV fields:", reader.fieldnames)

        # 行号从 1 开始数（更直观一点）
        for idx, row in enumerate(reader, start=1):
            origin = row.get("Origin")
            dest = row.get("Destination")

            # 跳过字段缺失的行
            if not origin or not dest:
                continue

            if panel_type == "large":
                if 1 <= idx <= 100:
                    routes.append((origin, dest))
                elif idx > 100:
                    # large 只要前 100 行，后面的可以直接 break
                    break

            elif panel_type == "medium":
                if 101 <= idx <= 500:
                    routes.append((origin, dest))
                elif idx > 500:
                    # medium 只要到 500 行
                    break

            elif panel_type == "small":
                # 小运力后面再处理，这里先不返回任何航线
                pass
    print(f"panel_type={panel_type}, routes_count={len(routes)}")
    return routes


from datetime import date

def build_periods(time_granularity: str, start_year: int, years: int):
    """
    根据粒度 & 开始年份 & 年数，生成：
      - forecast_dates: 用于查表的 Date 列表
      - labels: 前端展示用的字符串列表

    约定：
      years 参数表示“多少年”的跨度：
        yearly:    一年一个点，总数 = years
        quarterly: 一年四个季度，总数 = years * 4
        monthly:   一年十二个月，总数 = years * 12
    """
    forecast_dates = []
    labels = []

    if years <= 0:
        return forecast_dates, labels

    if time_granularity == "yearly":
        for y in range(start_year, start_year + years):
            d = date(y, 1, 1)
            forecast_dates.append(d)
            labels.append(str(y))

    elif time_granularity == "quarterly":
        for y in range(start_year, start_year + years):
            for q in range(1, 5):  # Q1~Q4
                month = (q - 1) * 3 + 1
                d = date(y, month, 1)
                forecast_dates.append(d)
                labels.append(f"{y}-Q{q}")

    elif time_granularity == "monthly":
        for y in range(start_year, start_year + years):
            for m in range(1, 13):  # 1~12 月
                d = date(y, m, 1)
                forecast_dates.append(d)
                labels.append(f"{y}-{m:02d}")

    else:
        raise ValueError("不支持的时间粒度")

    return forecast_dates, labels
from django.db.models import Q
@api_view(['GET'])
def forecast_panels_view(request):
    """
    GET /api/forecast-panels/?time_granularity=monthly&start_year=2024&steps=12&panels=large,medium

    参数：
      - time_granularity: monthly | quarterly | yearly
      - start_year: 开始年份 (int)
      - steps: 时间步数 (int)
      - panels: 需要返回的面板类型
          * 支持 ?panels=large,medium
          * 也支持 ?panels=large&panels=medium

    返回：
    {
      "success": true,
      "route_length":,
      "data": {
        "forecast_time": "2024-08-01T10:20:30",
        "time_points": ["2024-01", "2024-02", ...],
        "panels": {
          "large": {
            "headers": ["route", "2024-01", "2024-02", ...],
            "rows": [
              ["SHA-PEK", 1200, 1300, ...],   # 现在是 SHA-PEK + PEK-SHA 的和
              ["PVG-CAN", 900, 920, ...]
            ]
          },
          "medium": {
            "headers": [...],
            "rows": [...]
          },
          "small": { ... }
        }
      }
    }
    """
    try:
        gran = request.GET.get("time_granularity", "monthly")
        if gran not in ("monthly", "quarterly", "yearly"):
            return JsonResponse(
                {"success": False, "error": "time_granularity 必须为 monthly/quarterly/yearly"},
                status=400,
            )

        try:
            start_year = int(request.GET.get("start_year", "2024"))
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "start_year 必须是整数年份"},
                status=400,
            )

        try:
            steps = int(request.GET.get("steps", "12"))
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "steps 必须是整数"},
                status=400,
            )
        # 解析 panels 参数：同时兼容 panels=large,medium 和 panels=large&panels=medium
        raw_list = request.GET.getlist("panels")  # 可能是 ["large,medium,small"] 或 ["large", "medium"]
        panel_types = []

        for entry in raw_list:
            panel_types.extend(
                [p.strip() for p in entry.split(",") if p.strip()]
            )

        if not panel_types:
            raw = request.GET.get("panels", "")
            if raw:
                panel_types = [p.strip() for p in raw.split(",") if p.strip()]

        if not panel_types:
            panel_types = ["large"]  # 默认

        # 生成时间轴
        forecast_dates, time_labels = build_periods(gran, start_year, steps)

        # 选择对应模型
        model_map = {
            "monthly": ForecastMonthly,
            "quarterly": ForecastQuarterly,
            "yearly": ForecastYearly,
        }
        ModelCls = model_map[gran]

        # 先根据需要的 panels 从 csv 拿到所有航线
        panel_routes = {}
        all_routes = set()
        for p in panel_types:
            if p == "small":
                # 小运力：直接用数据库中的汇总航线 other-other
                routes = [("OTHER", "OTHER")]
            else:
                # large / medium 还是按 csv 来
                routes = get_routes_from_csv(p)

            panel_routes[p] = routes
            all_routes.update(routes)

        # 如果一个航线都没有，就直接返回空结构
        if not all_routes:
            return JsonResponse(
                {
                    "success": True,
                    "data": {
                        "forecast_time": None,
                        "time_points": time_labels,
                        "panels": {p: {"headers": ["route"] + time_labels, "rows": []} for p in panel_types},
                    },
                }
            )

        # 获取 route_ranking.csv 的总行数
        route_length = 0
        if os.path.exists(ROUTE_RANKING_CSV):
            with open(ROUTE_RANKING_CSV, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                route_length = sum(1 for row in reader)

        # ======================
        # 1. 构造双向航线查询条件：od / do 都查
        # ======================
        route_filter = Q()
        for o, d in all_routes:
            route_filter |= Q(origin=o, destination=d) | Q(origin=d, destination=o)

        # 批量查询这些航线在指定 forecast_dates 的 ask
        qs = (
            ModelCls.objects.filter(route_filter, forecast_date__in=forecast_dates)
            .values("origin", "destination", "forecast_date", "ask")
        )

        # ======================
        # 2. 构造双向合并后的 map:
        #    (无向航线 key: 规范化后的 o, d, forecast_date) -> ask(od) + ask(do)
        # ======================
        ask_map = {}
        for row in qs:
            o = row["origin"]
            d = row["destination"]
            fdate = row["forecast_date"]
            val = row["ask"]
            if val is None:
                val = 0
            else:
                val = round(val)

            # 规范化成无向航线 key，例如 SHA-PEK 和 PEK-SHA 都归为 (PEK, SHA) 或 (SHA, PEK)
            if o <= d:
                co, cd = o, d
            else:
                co, cd = d, o

            key = (co, cd, fdate)
            ask_map[key] = ask_map.get(key, 0) + val

        # 获取最新一次成功的预测时间（用 created_at）
        last_log = ForecastUpdateLog.objects.filter(status=2).order_by("-created_at").first()
        if last_log:
            forecast_time_str = last_log.created_at.isoformat()
        else:
            forecast_time_str = None

        # 组装返回的 panels 结构
        panels_data = {}
        for p in panel_types:
            routes = panel_routes.get(p, [])
            headers = ["route"] + time_labels
            rows = []

            for o, d in routes:
                route_name = f"{o}-{d}"

                # 对应到无向航线 key，用于拿到 od+do 的和
                if o <= d:
                    co, cd = o, d
                else:
                    co, cd = d, o

                values = []
                for fdate in forecast_dates:
                    key = (co, cd, fdate)
                    val = ask_map.get(key, 0)  # 没有的为 0
                    values.append(val)
                rows.append([route_name] + values)

            panels_data[p] = {
                "headers": headers,
                "rows": rows,
            }

        return JsonResponse(
            {
                "success": True,
                "data": {
                    "route_length": route_length,  # 返回航线总数
                    "forecast_time": forecast_time_str,
                    "time_points": time_labels,
                    "panels": panels_data,
                },
            }
        )

    except Exception as e:
        # 出异常时返回 500，方便调试
        import traceback

        return JsonResponse(
            {
                "success": False,
                "error": "服务器内部错误",
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
            status=500,
        )




@api_view(['GET'])
def get_forecast_update_logs(request):
    """
    获取预测更新日志记录
    参数:
        limit (可选): 需要返回的记录数，默认3条
    返回:
        logs: 最近N条日志记录列表，每条包含id、三个时间字段、状态（文字形式）
        last_success: 最后一条状态为2（成功）的记录
        can_update: 当前是否可以更新（布尔值）
    """
    try:
        # 获取limit参数，默认为3
        limit = int(request.GET.get('limit', 3))
        
        # 获取最近N条记录（按创建时间倒序）
        logs = ForecastUpdateLog.objects.all().order_by('-created_at')[:limit]
        
        # 构建日志列表
        logs_data = []
        for log in logs:
            logs_data.append({
                'id': log.id,
                'created_at': log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else None,
                'start_time': log.start_time.strftime("%Y-%m-%d %H:%M:%S") if log.start_time else None,
                'end_time': log.end_time.strftime("%Y-%m-%d %H:%M:%S") if log.end_time else None,
                'status': log.get_status_display(),  # 获取状态文字形式
            })
        
        # 获取最后一条状态为2（成功）的记录（按创建时间倒序）
        last_success_log = ForecastUpdateLog.objects.filter(status=2).order_by('-created_at').first()
        last_success_data = None
        if last_success_log:
            last_success_data = {
                'id': last_success_log.id,
                'created_at': last_success_log.created_at.strftime("%Y-%m-%d %H:%M:%S") if last_success_log.created_at else None,
                'start_time': last_success_log.start_time.strftime("%Y-%m-%d %H:%M:%S") if last_success_log.start_time else None,
                'end_time': last_success_log.end_time.strftime("%Y-%m-%d %H:%M:%S") if last_success_log.end_time else None,
                'status': last_success_log.get_status_display(),
            }
        
        # 判断当前是否可以更新（参考 trigger_update_forecast 的逻辑）
        TIMEOUT_HOURS = 48
        last_task = ForecastUpdateLog.objects.order_by('-created_at').first()
        can_update = True
        
        if last_task:
            # 如果是 Pending 或 Running
            if last_task.status in [0, 1]:
                # 检查是否超时 (防止死锁)
                time_since_start = timezone.now() - last_task.created_at
                if time_since_start.total_seconds() < TIMEOUT_HOURS * 3600:
                    # 确实正在跑，且没超时
                    can_update = False
        
        return JsonResponse({
            'success': True,
            'data': {
                'logs': logs_data,
                'last_success': last_success_data,
                'can_update': can_update,
            }
        })
        
    except ValueError:
        return JsonResponse({
            'success': False,
            'message': 'limit参数必须是有效的整数'
        }, status=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'服务器错误: {str(e)}'
        }, status=500)

# 获取机型数据表
def get_fleet_params_ordered():
    """
    从 FleetParam 表中获取所有机队，按 avg_seats 递增排序
    返回：OrderedDict[fleet_type] = FleetParam 实例
    """
    qs = FleetParam.objects.all().order_by("avg_seats")

    result = OrderedDict()
    for fp in qs:
        result[fp.fleet_type] = fp
    return result
# 获取映射μ
FLEET_PROP_CSV = os.path.join(settings.BASE_DIR, "Predict_Datas", "fleet_proportions.csv")
FLEET_COLS = [
    "大型涡扇支线客机",
    "小型窄体客机",
    "中型窄体客机",
    "大型窄体客机",
    "小型宽体客机",
    "中型宽体客机",
    "大型宽体客机",
]
def load_fleet_mu_map():
    """
    读取 fleet_proportions.csv，返回:
    {
      (origin, destination): {
          "大型涡扇支线客机": μ1,
          "小型窄体客机": μ2,
          ...
      },
      ...
    }
    自动尝试多种常见编码，避免 gbk / utf-8 报错。
    """
    mu_map = {}

    if not os.path.exists(FLEET_PROP_CSV):
        return mu_map

    # 依次尝试这些编码
    encodings_to_try = ("utf-8", "utf-8-sig", "gbk", "gb2312", "cp1252")

    last_err = None

    for enc in encodings_to_try:
        try:
            with open(FLEET_PROP_CSV, newline="", encoding=enc) as f:
                reader = csv.DictReader(f)

                tmp_map = {}
                for row in reader:
                    origin = row.get("origin")
                    dest = row.get("destination")
                    if not origin or not dest:
                        continue

                    key = (origin, dest)
                    inner = {}
                    for col in FLEET_COLS:
                        val = row.get(col)
                        if val in (None, "", "NaN"):
                            continue
                        try:
                            inner[col] = float(val)
                        except ValueError:
                            continue

                    tmp_map[key] = inner

            # 如果成功读完，赋值给 mu_map 并返回
            mu_map = tmp_map
            # 你想的话可以打个 log 看最终使用的是哪个编码
            print(f"[load_fleet_mu_map] 使用编码读取成功: {enc}")
            return mu_map

        except UnicodeDecodeError as e:
            last_err = e
            # 换下一个编码继续试
            continue

    # 如果所有编码都失败，就把最后一次错误抛出去（方便你在返回里看到）
    raise last_err if last_err else UnicodeDecodeError(
        "unknown", b"", 0, 1, "无法识别文件编码"
    )


@api_view(['GET'])
def fleet_forecast_view(request):
    """
    GET /api/fleet_forecast_view/year=2024&panels=large,medium,all

    参数：
      - year: 开始年份 (int)
      - panels: 需要返回的面板类型
          * 支持 ?panels=large,medium
          * 也支持 ?panels=large&panels=medium

    逻辑：
      1. 按年份从 ForecastYearly 查 ASK（此处已改为双向航线 OD/DO 相加）
      2. 从 fleet_proportions.csv 找到对应机型的 μ
      3. 对每条航线、每个机型计算：
         - val_seats = ask * μ / avg_seats
         - val_speed = ask * μ / avg_speed
         - val_uti   = ask * μ / avg_uti
      4. 不做跨航线的相加，直接把这些结果按 panel 返回
    """
    try:
        # ------------ 1. year 参数 ------------
        try:
            start_year = int(request.GET.get("year", "2024"))
        except ValueError:
            return JsonResponse(
                {"success": False, "error": "year 必须是整数年份"},
                status=400,
            )

        # ------------ 2. panels 参数 ------------
        raw_list = request.GET.getlist("panels")  # 可能是 ["large,medium,all"] 或 ["large", "medium"]
        panel_types = []

        for entry in raw_list:
            panel_types.extend(
                [p.strip() for p in entry.split(",") if p.strip()]
            )

        if not panel_types:
            raw = request.GET.get("panels", "")
            if raw:
                panel_types = [p.strip() for p in raw.split(",") if p.strip()]

        if not panel_types:
            panel_types = ["large"]  # 默认

        valid_panels = {"large", "medium", "all"}
        panel_types = [p for p in panel_types if p in valid_panels]
        if not panel_types:
            return JsonResponse(
                {"success": False, "error": "panels 必须是 large/medium/all"},
                status=400,
            )

        # ------------ 3. 每个 panel 对应的航线列表 ------------
        panel_routes = {}
        all_routes = set()
        for p in panel_types:
            if p == "all":
                # all 面板：只返回 ALL-ALL 这一条
                routes = [("ALL", "ALL")]
            else:
                # large / medium 还是按 csv 来
                routes = get_routes_from_csv(p)

            panel_routes[p] = routes
            all_routes.update(routes)

        if not all_routes:
            return JsonResponse(
                {
                    "success": False,
                    "error": "没有航线",
                },
                status=400,
            )

        # ------------ 5. 按年份从 ForecastYearly 查询 ASK（双向相加） ------------
        ModelCls = ForecastYearly

        # 查询条件：每条航线的 OD / DO 都查出来
        route_filter = Q()
        for o, d in all_routes:
            route_filter |= Q(origin=o, destination=d) | Q(origin=d, destination=o)

        qs = (
            ModelCls.objects.filter(route_filter, forecast_date__year=start_year)
            .values("origin", "destination", "ask")
        )

        # 无向航线 key：(co, cd) -> ask_od + ask_do
        ask_map = {}
        for row in qs:
            o = row["origin"]
            d = row["destination"]
            val = row["ask"]
            val = float(val) if val is not None else 0.0

            # 规范化为无向航线 key，例如 SHA-PEK / PEK-SHA 都归一为 (SHA, PEK)
            if o <= d:
                co, cd = o, d
            else:
                co, cd = d, o

            key = (co, cd)
            ask_map[key] = ask_map.get(key, 0.0) + val

        # ------------ 6. 最新一次成功预测时间 ------------
        last_log = ForecastUpdateLog.objects.filter(status=2).order_by("-created_at").first()
        if last_log:
            forecast_time_str = last_log.created_at.isoformat()
        else:
            forecast_time_str = None

        # ------------ 7. 读 μ（机队比例）+ 机队参数 ------------
        mu_map = load_fleet_mu_map()          # {(o,d): {fleet_type: μ}}
        fleet_params = get_fleet_params_ordered()  # OrderedDict[fleet_type] = FleetParam

        # ------------ 8. 按 panel、按航线、按机型 计算 ask*μ/avg_xxx ------------
        panels_data = {}

        # 表头：route, 每个机队一列（值为 float_num）
        headers = ["route"] + FLEET_COLS

        for p in panel_types:
            routes = panel_routes[p]
            rows = []

            for (o, d) in routes:
                # ASK 使用双向相加后的无向 key
                if o <= d:
                    co, cd = o, d
                else:
                    co, cd = d, o
                ask_val = ask_map.get((co, cd), 0.0)

                # μ 仍然按配置的 (o, d) 方向来取
                mu_for_route = mu_map.get((o, d), {})

                route_name = f"{o}-{d}"
                row = [route_name]

                # 按 FLEET_COLS 的顺序依次算每个机队的 float_num
                for fleet_type in FLEET_COLS:
                    mu = mu_for_route.get(fleet_type, 0.0)
                    fp = fleet_params.get(fleet_type)

                    if (
                        not fp
                        or mu == 0
                        or ask_val == 0
                        or fp.avg_seats in (None, 0)
                        or fp.avg_speed in (None, 0)
                        or fp.avg_uti in (None, 0)
                    ):
                        float_num = 0.0
                    else:
                        avg_seats = float(fp.avg_seats)
                        avg_speed = float(fp.avg_speed)
                        avg_uti = float(fp.avg_uti)

                        # 飞机数量 float_num = ask * μ / (avg_seats * avg_speed * avg_uti * 365)
                        float_num = int(ask_val * mu / (avg_seats * avg_speed * avg_uti * 365))

                    row.append(round(float_num, 6))

                rows.append(row)

            panels_data[p] = {
                "headers": headers,
                "rows": rows,
            }

        # ------------ 9. 返回 ------------
        return JsonResponse(
            {
                "success": True,
                "data": {
                    "forecast_time": forecast_time_str,
                    "year": start_year,
                    "panels": panels_data,
                },
            }
        )

    except Exception as e:
        # 出异常时返回 500，方便调试
        import traceback

        return JsonResponse(
            {
                "success": False,
                "error": "服务器内部错误",
                "message": str(e),
                "traceback": traceback.format_exc(),
            },
            status=500,
        )


@api_view(['GET'])
def fleet_param_list_view(request):
    """
    GET /api/fleet-params/

    返回所有 FleetParam 记录：
    {
      "success": true,
      "data": [
        {
          "fleet_type": "大型涡扇支线客机",
          "avg_seats": 76.0,
          "avg_speed": 586.0,
          "avg_uti": 8.8
        },
        ...
      ]
    }
    """
    objs = FleetParam.objects.all().order_by("avg_seats")

    data = []
    for obj in objs:
        data.append({
            "fleet_type": obj.fleet_type,
            "avg_seats": float(obj.avg_seats) if obj.avg_seats is not None else None,
            "avg_speed": float(obj.avg_speed) if obj.avg_speed is not None else None,
            "avg_uti": float(obj.avg_uti)     if obj.avg_uti   is not None else None,
        })

    return JsonResponse({"success": True, "data": data})

@api_view(['POST'])
@csrf_exempt
def fleet_param_update_view(request):
    """
    POST /api/fleet-params/

    请求体示例：
    {
      "data": [
        {
          "fleet_type": "大型涡扇支线客机",
          "avg_seats": 76.0,
          "avg_speed": 586.0,
          "avg_uti": 8.8
        },
        ...
      ]
    }

    逻辑：
      - 把现有 FleetParam 全部清空
      - 用 data 里这批数据重新写入
    """
    # 1. 解析 JSON
    try:
        body = request.body.decode("utf-8") or "{}"
        payload = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"success": False, "error": "请求体不是合法 JSON"},
            status=400,
        )

    items = payload.get("data")
    # 兼容前端直接传数组的情况：直接把整个 payload 当作 list
    if items is None and isinstance(payload, list):
        items = payload

    if not isinstance(items, list):
        return JsonResponse(
            {"success": False, "error": "data 字段必须是列表"},
            status=400,
        )

    objs = []
    for idx, item in enumerate(items):
        fleet_type = item.get("fleet_type")
        if not fleet_type:
            return JsonResponse(
                {"success": False, "error": f"第 {idx} 条记录缺少 fleet_type"},
                status=400,
            )

        avg_seats = item.get("avg_seats")
        avg_speed = item.get("avg_speed")
        avg_uti = item.get("avg_uti")

        obj = FleetParam(
            fleet_type=fleet_type,
            avg_seats=Decimal(str(avg_seats)) if avg_seats is not None else None,
            avg_speed=Decimal(str(avg_speed)) if avg_speed is not None else None,
            avg_uti=Decimal(str(avg_uti)) if avg_uti is not None else None,
        )
        objs.append(obj)

    # 2. 覆盖写入
    with transaction.atomic():
        FleetParam.objects.all().delete()
        FleetParam.objects.bulk_create(objs)

    # 3. 返回刚写入的数据（方便前端确认）
    resp_data = [
        {
            "fleet_type": o.fleet_type,
            "avg_seats": float(o.avg_seats) if o.avg_seats is not None else None,
            "avg_speed": float(o.avg_speed) if o.avg_speed is not None else None,
            "avg_uti": float(o.avg_uti) if o.avg_uti is not None else None,
        }
        for o in objs
    ]

    return JsonResponse(
        {
            "success": True,
            "count": len(objs),
            "data": resp_data,
        }
    )

