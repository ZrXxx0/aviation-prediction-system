import os
import pickle
import json
import pandas as pd
import numpy as np
from datetime import datetime
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist

import warnings
warnings.filterwarnings("ignore")

# 添加正确的导入路径，解决pickle加载时的模块依赖问题
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
predictive_algorithm_dir = os.path.join(current_dir, 'predictive_algorithm')
if predictive_algorithm_dir not in sys.path:
    sys.path.insert(0, predictive_algorithm_dir)

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
                result = _execute_single_prediction(pred)
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

def _execute_single_prediction(prediction_request):
    """
    执行单个预测请求
    
    Args:
        prediction_request: 包含预测参数的字典
        
    Returns:
        包含模型信息和预测结果的字典
    """
    
    origin_airport = prediction_request['origin_airport'].upper()
    destination_airport = prediction_request['destination_airport'].upper()
    time_granularity = prediction_request['time_granularity']
    prediction_periods = prediction_request['prediction_periods']
    model_id = prediction_request['model_id']
    
    # 从数据库获取模型信息
    try:
        model_info = RouteModelInfo.objects.get(model_id=model_id)
    except RouteModelInfo.DoesNotExist:
        raise Exception(f"未找到模型ID: {model_id}")
    
    # 验证模型是否匹配请求的航线和时间粒度
    if (model_info.origin_airport != origin_airport or 
        model_info.destination_airport != destination_airport or
        model_info.time_granularity != time_granularity):
        raise Exception(f"模型 {model_id} 与请求的航线或时间粒度不匹配")
    
    # 构建根目录路径 - 使用更可靠的路径构建方法
    current_dir = os.path.dirname(os.path.abspath(__file__))  # 当前文件所在目录
    base_dir = os.path.join(os.path.dirname(current_dir), 'AirlineModels')  # 上级目录下的AirlineModels
    
    # 加载模型文件
    model_file_path = os.path.join(base_dir, model_info.model_file_path)
    preprocessor_file_path = os.path.join(base_dir, model_info.preprocessor_file_path)
    feature_builder_file_path = os.path.join(base_dir, model_info.feature_builder_file_path)
    meta_file_path = os.path.join(base_dir, model_info.meta_file_path)
    raw_data_file_path = os.path.join(base_dir, model_info.raw_data_file_path)
    
    # 检查文件是否存在
    required_files = [model_file_path, preprocessor_file_path, feature_builder_file_path, 
                     meta_file_path, raw_data_file_path]
    for file_path in required_files:
        if not os.path.exists(file_path):
            raise Exception(f"文件不存在: {file_path}")
    
    try:
        # 加载模型组件
        with open(model_file_path, "rb") as f:
            model = pickle.load(f)
        
        with open(preprocessor_file_path, "rb") as f:
            preprocessor = pickle.load(f)
        
        with open(feature_builder_file_path, "rb") as f:
            feature_builder = pickle.load(f)
        
        with open(meta_file_path, "r", encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 加载原始数据
        latest_data = pd.read_csv(raw_data_file_path)
        date_col = metadata.get('date_column', 'YearMonth')
        latest_data[date_col] = pd.to_datetime(latest_data[date_col])
        
    except Exception as e:
        import traceback
        error_msg = f"加载模型文件失败: {str(e)}\n详细错误信息:\n{traceback.format_exc()}"
        raise Exception(error_msg)
    
    # 获取预测所需的信息
    feature_cols = metadata.get('feature_columns', [])
    target_col = metadata.get('target_column', 'Seats')
    last_complete_date = pd.to_datetime(metadata.get('last_complete_date', latest_data[date_col].max()))
    
    # 根据时间粒度调整预测期数
    if time_granularity == 'quarterly':
        adjusted_periods = prediction_periods
    elif time_granularity == 'yearly':
        adjusted_periods = prediction_periods
    else:
        adjusted_periods = prediction_periods
    
    # 调整最后完整日期到对应的时间粒度
    if time_granularity == 'quarterly':
        while last_complete_date.month not in [3, 6, 9, 12]:
            last_complete_date -= pd.DateOffset(months=1)
    elif time_granularity == 'yearly':
        while last_complete_date.month != 12:
            last_complete_date -= pd.DateOffset(months=1)
    
    # 执行预测
    future_preds = []
    current_data = latest_data.copy()
    
    for i in range(adjusted_periods):
        # 计算下一个时间点
        if time_granularity == 'monthly':
            offset = pd.DateOffset(months=1)
        elif time_granularity == 'quarterly':
            offset = pd.DateOffset(months=3)
        else:  # yearly
            offset = pd.DateOffset(years=1)
        
        next_date = last_complete_date + offset
        
        # 创建新的数据行
        next_row = {date_col: next_date}
        for col in current_data.columns:
            if col != date_col:
                next_row[col] = np.nan
        
        # 添加新行并处理
        current_data = pd.concat([current_data, pd.DataFrame([next_row])], ignore_index=True)
        current_data = preprocessor.fit_transform(current_data)
        current_data = feature_builder.fit_transform(current_data)
        
        # 预测
        latest_input = current_data.iloc[[-1]][feature_cols]
        next_pred = model.predict(latest_input)[0]
        
        # 更新数据
        current_data.loc[current_data.index[-1], target_col] = next_pred
        
        future_preds.append({
            'YearMonth': next_date,
            'Predicted': next_pred
        })
        
        last_complete_date = next_date
    
    future_df = pd.DataFrame(future_preds)
    
    # 构建模型信息返回
    model_info_response = {
        'model_id': model_info.model_id,
        'origin_airport': model_info.origin_airport,
        'destination_airport': model_info.destination_airport,
        'time_granularity': model_info.time_granularity,
        'model_type': metadata.get('model_type', 'LightGBM'),
        'feature_count': len(feature_cols),
        'training_samples': metadata.get('training_samples', len(latest_data)),
        'test_samples': metadata.get('test_samples', 0),
        'train_mae': model_info.train_mae,
        'train_rmse': model_info.train_rmse,
        'train_mape': model_info.train_mape,
        'train_r2': model_info.train_r2,
        'test_mae': model_info.test_mae,
        'test_rmse': model_info.test_rmse,
        'test_mape': model_info.test_mape,
        'test_r2': model_info.test_r2,
        'train_start_time': model_info.train_start_time.strftime('%Y-%m-%d') if model_info.train_start_time else None,
        'train_end_time': model_info.train_end_time.strftime('%Y-%m-%d') if model_info.train_end_time else None,
        'last_complete_date': metadata.get('last_complete_date')
    }
    
    # 构建历史数据
    historical_data = []
    for _, row in latest_data.iterrows():
        historical_data.append({
            'time_point': _fmt_label(row[date_col], time_granularity),
            'value': int(row[target_col]) if pd.notna(row[target_col]) else None
        })
    
    # 构建未来预测数据
    future_predictions = []
    for _, row in future_df.iterrows():
        future_predictions.append({
            'time_point': _fmt_label(row['YearMonth'], time_granularity),
            'value': int(row['Predicted']) if pd.notna(row['Predicted']) else None
        })
    
    # 返回结果
    return {
        'model_info': model_info_response,
        'prediction_results': {
            'historical_data': historical_data,
            'future_predictions': future_predictions
        }
    }
