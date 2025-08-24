import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
import matplotlib.pyplot as plt
from datetime import datetime
import pickle
import json

from .time_granularity import TimeGranularityController
from .TS_model import ARIMAModel
from .FeatureEngineer import DataPreprocessor, FeatureBuilder, AirlineRouteModel
from .create_model import get_model
from .pretrain_single_route import load_data_from_database

import warnings
warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def formal_train_single_route(origin, destination, time_granularity, pretrained_metadata_path):
    """
    正式训练单条航线的完整流程，使用预训练模型的元数据参数

    :param origin: 起始机场代码 (如 'CAN')
    :param destination: 目标机场代码 (如 'PEK')
    :param time_granularity: 时间粒度
    :param pretrained_metadata_path: 预训练模型元数据文件路径
    :return: 训练状态 (成功/失败) 和结果信息
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/predict/predictive_algorithm/
    model_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'AirlineModels')  # backend/AirlineModels
    EXISTING_MODEL_DIR = os.path.join(model_dir, 'Existing_Models')

    # 预训练的元数据地址
    PRE_TRAINED_MODEL_DIR = os.path.join(model_dir, 'Pre_trained_Models')
    full_pretrained_metadata_path = os.path.join(PRE_TRAINED_MODEL_DIR, pretrained_metadata_path)

    try:
        # 加载预训练模型的元数据
        print(f"加载预训练模型元数据: {full_pretrained_metadata_path}")
        if not os.path.exists(full_pretrained_metadata_path):
            print(f"! 预训练模型元数据文件不存在: {full_pretrained_metadata_path}")
            return False, "预训练模型元数据文件不存在"
        
        with open(full_pretrained_metadata_path, 'r', encoding='utf-8') as f:
            pretrained_metadata = json.load(f)
        
        # print("预训练模型元数据加载成功")
        # print(f"元数据内容: {json.dumps(pretrained_metadata, ensure_ascii=False, indent=2)}")
        model_type = pretrained_metadata["model_type"]
        # 创建时间粒度和模型类型的子目录
        granularity_model_dir = os.path.join(EXISTING_MODEL_DIR, f"{time_granularity}_{model_type}")
        os.makedirs(granularity_model_dir, exist_ok=True)

        # 生成时间戳（精确到秒）
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')

        # 创建最终的航线目录
        route_dir = os.path.join(granularity_model_dir, f"{origin}_{destination}_{timestamp}")
        full_model_id = f"{origin}_{destination}_{timestamp}"
        os.makedirs(route_dir, exist_ok=True)

        # 从元数据中提取关键参数
        # 1. 提取ARIMA order参数
        arima_order = pretrained_metadata.get("arima_order", (1, 1, 1))
        # print(f"提取的ARIMA order参数: {arima_order}")
        
        # 2. 提取add_ts_forecast参数
        add_ts_forecast = pretrained_metadata.get("add_ts_forecast", True)
        # print(f"提取的add_ts_forecast参数: {add_ts_forecast}")
        
        # 3. 提取模型参数
        model_params = pretrained_metadata.get("model_params", {})
        # print(f"提取的模型参数: {model_params}")
        
        # 4. 提取完整配置信息（如果存在）
        complete_config = pretrained_metadata.get("complete_config", {})
        if complete_config:
            print(f"提取的完整配置: {json.dumps(complete_config, ensure_ascii=False, indent=2)}")
            # 如果存在完整配置，优先使用完整配置中的参数
            if "arima_order" in complete_config:
                arima_order = complete_config["arima_order"]
            if "add_ts_forecast" in complete_config:
                add_ts_forecast = complete_config["add_ts_forecast"]
            if "model_params" in complete_config:
                model_params = complete_config["model_params"]

        # 从数据库加载数据
        # print("从数据库加载数据...")
        domestic = load_data_from_database(origin, destination)

        if domestic is None:
            print(f"! 无法从数据库加载航线 {origin}-{destination} 的数据")
            return False, "无法从数据库加载数据"

        # 检查航线数据是否存在
        mask = (domestic['Origin'] == origin) & (domestic['Destination'] == destination)
        route_data = domestic[mask].copy()

        if route_data.empty:
            print(f"! 未找到航线 {origin}-{destination} 的数据")
            return False, "航线数据不存在"

        # print(f"找到 {len(route_data)} 条航线记录")

        # print(f"创建输出目录: {route_dir}")

        # 初始化组件
        preprocessor = DataPreprocessor(
            fill_method='interp',
            normalize=False,
            non_economic_tail_window=6,
        )

        granularity_controller = TimeGranularityController(time_granularity)

        # 使用从元数据中提取的ARIMA order参数
        ts_model = ARIMAModel(
            order=arima_order,
            freq=granularity_controller.get_freq()
        )

        # 使用从元数据中提取的add_ts_forecast参数
        feature_builder = FeatureBuilder(
            granularity_controller=granularity_controller,
            add_ts_forecast=add_ts_forecast,
            ts_model=ts_model
        )

        route_processor = AirlineRouteModel(
            data=domestic,
            preprocessor=preprocessor,
            feature_builder=feature_builder,
            granularity=time_granularity
        )

        # 使用全部数据重新训练
        print("使用全部数据重新训练模型...")
        X_full, y_full, _, _, data_with_features_full = route_processor.prepare_data(
            origin=origin,
            destination=destination,
            test_size=0
        )
        
        # 使用从元数据中提取的模型参数创建模型
        model_full = get_model(time_granularity, model_type, model_params)
        # print(f"使用参数创建模型: {model_params}")
        
        # 训练模型
        # print("开始训练模型...")
        model_full.fit(X_full, y_full)
        # print("模型训练完成")

        # 保存模型文件
        # print("保存模型文件...")
        with open(os.path.join(route_dir, "model.pkl"), "wb") as f:
            pickle.dump(model_full, f)

        with open(os.path.join(route_dir, "preprocessor.pkl"), "wb") as f:
            pickle.dump(route_processor.preprocessor, f)

        with open(os.path.join(route_dir, "feature_builder.pkl"), "wb") as f:
            pickle.dump(route_processor.feature_builder, f)

        # 保存元数据
        metadata = {
            "feature_columns": X_full.columns.tolist(),
            "date_column": route_processor.date_col,
            "target_column": route_processor.target_col,
            "time_granularity": time_granularity,
            "model_type": model_type,
            "arima_order": arima_order,
            "add_ts_forecast": add_ts_forecast,
            "model_params": model_params,
            "last_complete_date": data_with_features_full[route_processor.date_col].max().strftime('%Y-%m-%d'),
            "feature_count": len(X_full.columns),
            "training_samples": len(X_full),
            "pretrained_metadata_source": pretrained_metadata_path,
            "training_datetime": datetime.now().isoformat()
        }
        with open(os.path.join(route_dir, "metadata.json"), "w", encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 保存最新数据
        latest_data = data_with_features_full.copy()
        latest_data.to_csv(os.path.join(route_dir, "latest_data.csv"), index=False)

        # 获取训练数据的日期范围
        train_start_date = data_with_features_full[route_processor.date_col].min()
        train_end_date = data_with_features_full[route_processor.date_col].max()
        
        # 返回成功状态和结果信息，包含创建RouteModelInfo所需的所有数据
        result_info = {
            # 基本信息
            "model_id": full_model_id,
            "origin_airport": origin,
            "destination_airport": destination,
            "time_granularity": time_granularity,
            "train_start_time": train_start_date,
            "train_end_time": train_end_date,
            "train_datetime": datetime.now(),
            
            # 文件路径（相对于EXISTING_MODEL_DIR的相对路径）
            "meta_file_path": os.path.relpath(os.path.join(route_dir, "metadata.json"), EXISTING_MODEL_DIR),
            "model_file_path": os.path.relpath(os.path.join(route_dir, "model.pkl"), EXISTING_MODEL_DIR),
            "raw_data_file_path": os.path.relpath(os.path.join(route_dir, "latest_data.csv"), EXISTING_MODEL_DIR),
            "preprocessor_file_path": os.path.relpath(os.path.join(route_dir, "preprocessor.pkl"), EXISTING_MODEL_DIR),
            "feature_builder_file_path": os.path.relpath(os.path.join(route_dir, "feature_builder.pkl"), EXISTING_MODEL_DIR),
        }

        print(f"正式训练完成！模型保存在: {route_dir}")
        return True, result_info

    except Exception as e:
        print(f"! 航线 {origin}-{destination} 训练失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, str(e)


# 使用示例
if __name__ == "__main__":
    # 示例：使用预训练模型的元数据参数进行正式训练
    # 假设预训练模型的元数据文件路径为：quarterly_lgb/CAN_PEK_20250813233015/metadata.json
    pretrained_metadata_path = "quarterly_lgb/CAN_PEK_20250813233015/metadata.json"
    
    print("=== 测试使用预训练模型参数进行正式训练 ===")
    success, result = formal_train_single_route("CAN", "PEK", "quarterly", "lgb", pretrained_metadata_path)
    
    if success:
        print(f"训练成功！结果: {result}")
    else:
        print(f"训练失败: {result}")