import os
import json
import pandas as pd
import numpy as np
import math
from datetime import datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
import copy

from .models import RouteModelInfo, PretrainRecord
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

# 获取预测模型函数
@require_GET
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
                'error': '未找到匹配的模型',
                'message': f'未找到从 {origin_airport} 到 {destination_airport} 的 {time_granularity} 粒度预测模型'
            }, status=404)
        
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

# 预测并返回结果函数
@csrf_exempt  # 仅用于测试，避免403错误
@require_POST
def forecast_route_view(request):
    """
    批量预测航线座位数
    
    请求体格式：
    {
        "predictions": [
            {
                "origin_airport": "CAN",  # 起始机场三字码
                "destination_airport": "PEK",  # 终点机场三字码
                "time_granularity": "monthly",  # 预测时间粒度 (yearly/quarterly/monthly)
                "prediction_periods": 12,  # 预测时间长度
                "model_id": "model_id_123"  # 使用的预测模型ID
            }
        ]
    }
    
    返回格式：
    {
        "success": true,
        "data": [
            {
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
                }
            }
        ]
    }
    """
    try:
        # 解析请求体
        data = json.loads(request.body)
        predictions = data.get('predictions', [])
        
        if not predictions:
            return JsonResponse({
                'error': '缺少预测请求',
                'message': '请提供 predictions 数组'
            }, status=400)
        
        # 验证每个预测请求
        for i, pred in enumerate(predictions):
            required_fields = ['origin_airport', 'destination_airport', 'time_granularity', 'prediction_periods', 'model_id']
            missing_fields = [field for field in required_fields if field not in pred]
            
            if missing_fields:
                return JsonResponse({
                    'error': f'预测请求 {i+1} 缺少必要字段',
                    'message': f'缺少字段: {", ".join(missing_fields)}'
                }, status=400)
            
            # 验证时间粒度
            if pred['time_granularity'] not in ['yearly', 'quarterly', 'monthly']:
                return JsonResponse({
                    'error': f'预测请求 {i+1} 无效的时间粒度',
                    'message': 'time_granularity 必须是 yearly, quarterly 或 monthly 之一'
                }, status=400)
            
            # 验证预测期数
            if not isinstance(pred['prediction_periods'], int) or pred['prediction_periods'] <= 0:
                return JsonResponse({
                    'error': f'预测请求 {i+1} 无效的预测期数',
                    'message': 'prediction_periods 必须是正整数'
                }, status=400)
        
        # 执行预测
        results = []
        for pred in predictions:
            try:
                result = predict_single_route(pred)
                results.append(result)
            except Exception as e:
                # 如果单个预测失败，记录错误但继续处理其他预测
                import traceback
                error_details = {
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'request': pred
                }
                results.append(error_details)
        
        return JsonResponse({
            'success': True,
            'data': results
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': '无效的JSON格式',
            'message': '请求体必须是有效的JSON格式'
        }, status=400)
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': '服务器内部错误',
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc()
        }, status=500)


# 预测并返回结果函数+层级对齐
@csrf_exempt
@require_POST
def forecast_route_view2(request):
    """
        批量预测航线座位数（支持可选“层级对齐”）

        请求体格式：
        {
            "hierarchy_reconcile": 1,                 // 0=不对齐(直接转调原接口)；1=进行层级对齐
            "reconcile_algo": "linear",               // 可选："linear"(默认) 或 "mint"
            "predictions": [
                {
                    "origin_airport": "CAN",          // 起始机场三字码
                    "destination_airport": "PEK",     // 终点机场三字码
                    "prediction_periods": 12,         // 预测未来期数（正整数）
                    "monthly_model_id": "M_ID_123",   // 月度模型ID
                    "quarterly_model_id": "Q_ID_456"  // 季度模型ID
                }
            ]
        }

        说明：
        - 当 hierarchy_reconcile=0 时，直接调用原有 forecast_route_view(request)，返回与原接口完全一致。
        - 当 hierarchy_reconcile=1 时：
          1) 同时调用月度与季度模型；
          2) 仅对“月度的未来段”做层级对齐（历史不变）；
          3) 返回三份结果：                          # [修改] 这里改成“三份”
             - data_monthly   ：月度结果（future 为对齐后的值，time_point 形如 "YYYY-MM"）
             - data_quarterly ：季度结果（future 由“对齐后的月度未来”按季度聚合得到，time_point 形如 "YYYY-Qn"）
             - data_yearly    ：年度结果（基于“季度数据”按年聚合得到，time_point 形如 "YYYY"）  # [新增]

        返回格式（hierarchy_reconcile=1 时）：
        {
            "success": true,
            "hierarchy_reconcile": 1,
            "data_monthly":   [ {...} ],
            "data_quarterly": [ {...} ],
            "data_yearly":    [ {...} ]
        }
    """

    try:
        data = json.loads(request.body)
        if int(data.get('hierarchy_reconcile', 0)) == 0:
            return forecast_route_view(request)  # 直接沿用旧接口

        algo = (data.get('reconcile_algo') or 'linear').lower()
        recon_fn = linear_reconcile_monthly_to_quarterly if algo != 'mint' else mint_reconcile_monthly_to_quarterly

        predictions = data.get('predictions', [])
        if not predictions:
            return JsonResponse({'error': '缺少预测请求', 'message': '请提供 predictions 数组'}, status=400)

        data_monthly, data_quarterly = [], []
        data_yearly = []  # 年度结果列表

        for i, pred in enumerate(predictions):
            # 必填（对齐模式）
            for f in ['origin_airport', 'destination_airport', 'prediction_periods', 'monthly_model_id', 'quarterly_model_id']:
                if f not in pred:
                    return JsonResponse({
                        'error': f'预测请求 {i+1} 缺少必要字段',
                        'message': f'缺少字段: {f}（hierarchy_reconcile=1 时必填）'
                    }, status=400)
            if not isinstance(pred['prediction_periods'], int) or pred['prediction_periods'] <= 0:
                return JsonResponse({
                    'error': f'预测请求 {i+1} 无效的预测期数',
                    'message': 'prediction_periods 必须是正整数'
                }, status=400)

            months = int(pred['prediction_periods'])      # 期望覆盖的“月数”
            q_periods = max(1, math.ceil(months / 3))     # 3个月=1季度，向上取整

            base = {
                'origin_airport': pred['origin_airport'],
                'destination_airport': pred['destination_airport'],
            }

            monthly_req = {
                **base,
                'time_granularity': 'monthly',
                'prediction_periods': months,             # 月度照传
                'model_id': pred['monthly_model_id'],
            }
            quarterly_req = {
                **base,
                'time_granularity': 'quarterly',
                'prediction_periods': q_periods,          # 季度用 ceil(months/3)
                'model_id': pred['quarterly_model_id'],
            }

            try:
                # 1) 调两套模型
                monthly_resp   = predict_single_route(monthly_req)
                quarterly_resp = predict_single_route(quarterly_req)

                # 2) 整成DF：YearMonth, Predicted, Set（月度）；YearMonth, Predicted（季度）
                pm = monthly_resp.get('prediction_results', {}) or {}
                hist_m = pm.get('historical_data', []) or []
                futu_m = pm.get('future_predictions', []) or []
                df_m = pd.DataFrame(
                    [{'YearMonth': h['time_point'], 'Predicted': h['value'], 'Set': 'History'} for h in hist_m] +
                    [{'YearMonth': f['time_point'], 'Predicted': f['value'], 'Set': 'Future'}  for f in futu_m],
                    columns=['YearMonth', 'Predicted', 'Set']
                )

                pq = quarterly_resp.get('prediction_results', {}) or {}
                q_hist = pq.get('historical_data', []) or []
                q_futu = pq.get('future_predictions', []) or []
                q_all = q_hist + q_futu
                df_q = pd.DataFrame(
                    [{'YearMonth': r['time_point'], 'Predicted': r['value']} for r in q_all],
                    columns=['YearMonth', 'Predicted']
                )

                # 3) 对齐（linear/mint）
                df_m_rec = recon_fn(df_m, df_q)

                # 4) 月度：历史不变；未来用 Predicted_Reconciled
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

                # 5) 季度结果：直接使用季度模型输出（避免跨界季度只算未来月的问题）
                # 原来这里是按 df_m_rec 的 Future 月份聚合得到 futu_out_q —— 删除那段
                # 直接取季度模型的历史和未来：
                hist_q = pq.get('historical_data', []) or []
                futu_out_q = pq.get('future_predictions', []) or []

                # 6) 年度聚合（基于“季度数据”）
                yearly_hist, yearly_futu = aggregate_quarterly_to_year_by_blocks(hist_q, futu_out_q)


                # 7) 组装返回（三份）
                monthly_item = copy.deepcopy(monthly_resp)
                if 'model_info' not in monthly_item: monthly_item['model_info'] = {}
                if 'prediction_results' not in monthly_item: monthly_item['prediction_results'] = {}
                monthly_item['model_info']['time_granularity'] = 'monthly'
                monthly_item['model_info']['model_id'] = pred['monthly_model_id']
                monthly_item['prediction_results']['historical_data'] = hist_out_m
                monthly_item['prediction_results']['future_predictions'] = futu_out_m

                quarterly_item = copy.deepcopy(quarterly_resp)
                if 'model_info' not in quarterly_item: quarterly_item['model_info'] = {}
                if 'prediction_results' not in quarterly_item: quarterly_item['prediction_results'] = {}
                quarterly_item['model_info']['time_granularity'] = 'quarterly'
                quarterly_item['model_info']['model_id'] = pred['quarterly_model_id']
                quarterly_item['prediction_results']['historical_data'] = hist_q
                quarterly_item['prediction_results']['future_predictions'] = futu_out_q

                yearly_item = {
                    'model_info': {
                        **(quarterly_item.get('model_info') or {}),
                        'time_granularity': 'yearly',
                        'model_id': pred['quarterly_model_id'],  # 来源于季度聚合
                    },
                    'prediction_results': {
                        'historical_data': yearly_hist,
                        'future_predictions': yearly_futu
                    }
                }

                data_monthly.append(monthly_item)
                data_quarterly.append(quarterly_item)
                data_yearly.append(yearly_item)

            except Exception as e:
                import traceback
                err = {
                    'error_message': str(e),
                    'error_type': type(e).__name__,
                    'traceback': traceback.format_exc(),
                    'request': pred
                }
                data_monthly.append(copy.deepcopy(err))
                data_quarterly.append(copy.deepcopy(err))
                data_yearly.append(copy.deepcopy(err))


        return JsonResponse({
            'success': True,
            'hierarchy_reconcile': 1,
            'data_monthly': data_monthly,
            'data_quarterly': data_quarterly,
            'data_yearly': data_yearly,
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
                'report_pdf': result.get('report_pdf', '')
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
                'message': f'航线 {origin}-{destination} 模型训练成功'
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
        
        # 设置模型类型（这里假设为lgb，可以根据需要调整）
        model_type = 'lgb'
        
        print(f"开始正式训练模型: {origin}-{destination}, 时间粒度: {time_granularity}")
        # print(f"使用预训练元数据: {meta_file_path}")
        
        success, result = formal_train_single_route(
            origin=origin,
            destination=destination,
            time_granularity=time_granularity,
            model_type=model_type,
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



@require_GET
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




