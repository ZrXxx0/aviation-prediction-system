import os
import pickle
import json
import pandas as pd
import numpy as np

from predict.models import RouteModelInfo

import warnings
warnings.filterwarnings("ignore")

# 添加正确的导入路径，解决pickle加载时的模块依赖问题
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
predictive_algorithm_dir = os.path.join(current_dir, 'predictive_algorithm')
if predictive_algorithm_dir not in sys.path:
    sys.path.insert(0, predictive_algorithm_dir)



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

def predict_single_route(prediction_request):
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
    current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/predict/predictive_algorithm/
    base_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)),'AirlineModels', 'Existing_Models')

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