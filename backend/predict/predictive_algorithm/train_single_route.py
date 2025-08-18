import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
import matplotlib.pyplot as plt
import pickle
import json
from time_granularity import TimeGranularityController

from .TS_model import ARIMAModel
from .model_evaluation import ModelEvaluator
from .FeatureEngineer import DataPreprocessor, FeatureBuilder, AirlineRouteModel
from .create_model import get_model

import warnings
warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

def train_single_route(origin, destination, config=None):
    """
    训练单条航线的完整流程
    
    :param origin: 起始机场代码 (如 'CAN')
    :param destination: 目标机场代码 (如 'PEK')
    :param config: 配置字典，如果为None则使用默认配置
    :return: 训练状态 (成功/失败) 和结果信息
    """
    
    # 默认配置
    if config is None:
        config = {
            "test_size": 12,
            "time_granularity": "quarterly",
            "add_ts_forecast": True,
            "future_periods": 36,
            "model_type": "lgb",
            "plot_results": True,
            "save_data": True,
            "base_save_dir": "./single_route_results"
        }
    
    print(f"\n=== 开始训练航线: {origin} -> {destination} ===")
    print(f"配置: {config}")
    
    try:
        # 数据路径
        DOMESTIC_DATA_PATH = './final_data_0729.csv'
        
        # 检查数据文件是否存在
        if not os.path.exists(DOMESTIC_DATA_PATH):
            print(f"! 数据文件不存在: {DOMESTIC_DATA_PATH}")
            return False, "数据文件不存在"
        
        # 加载数据
        print("加载数据集...")
        domestic = pd.read_csv(DOMESTIC_DATA_PATH, low_memory=False)
        
        # 检查航线数据是否存在
        mask = (domestic['Origin'] == origin) & (domestic['Destination'] == destination)
        route_data = domestic[mask].copy()
        
        if route_data.empty:
            print(f"! 未找到航线 {origin}-{destination} 的数据")
            return False, "航线数据不存在"
        
        print(f"找到 {len(route_data)} 条航线记录")
        
        # 创建航线专属目录
        route_dir = os.path.join(config["base_save_dir"], f"{origin}_{destination}")
        os.makedirs(route_dir, exist_ok=True)
        print(f"创建输出目录: {route_dir}")
        
        # 初始化组件
        preprocessor = DataPreprocessor(
            fill_method='interp',
            normalize=False,
            non_economic_tail_window=6,
        )
        
        granularity_controller = TimeGranularityController(config["time_granularity"])
        
        ts_model = ARIMAModel(
            order=(1,1,1),
            freq=granularity_controller.get_freq()
        )
        
        feature_builder = FeatureBuilder(
            granularity_controller=granularity_controller,
            add_ts_forecast=config["add_ts_forecast"],
            ts_model=ts_model
        )
        
        route_processor = AirlineRouteModel(
            data=domestic,
            preprocessor=preprocessor,
            feature_builder=feature_builder,
            granularity=config["time_granularity"]
        )
        
        # 准备数据
        print("准备训练和测试数据...")
        X_train, y_train, X_test, y_test, data_with_features = route_processor.prepare_data(
            origin=origin,
            destination=destination,
            test_size=config["test_size"]
        )
        
        if X_train is None or X_train.empty:
            print(f"! 航线 {origin}-{destination} 数据不足，无法训练")
            return False, "数据不足"
        
        print(f"训练集样本数: {len(X_train)}")
        print(f"测试集样本数: {len(X_test) if X_test is not None else 0}")
        print(f"特征数量: {len(X_train.columns)}")
        
        # 保存数据
        if config["save_data"]:
            print("保存训练和测试数据...")
            X_train.to_csv(os.path.join(route_dir, "X_train.csv"), index=False)
            X_test.to_csv(os.path.join(route_dir, "X_test.csv"), index=False)
            pd.DataFrame(y_train).to_csv(os.path.join(route_dir, "y_train.csv"), index=False)
            pd.DataFrame(y_test).to_csv(os.path.join(route_dir, "y_test.csv"), index=False)
            data_with_features.to_csv(os.path.join(route_dir, "data_with_features.csv"), index=False)
        
        # 训练模型
        print(f"训练 {config['model_type'].upper()} 模型...")
        model = get_model(config["time_granularity"], config["model_type"])
        model.fit(X_train, y_train)
        
        # 评估模型
        print("评估模型性能...")
        train_preds = model.predict(X_train)
        train_evaluator = ModelEvaluator(y_train, train_preds).calculate_metrics()
        
        test_preds = None
        test_evaluator = None
        if config["time_granularity"] != 'yearly' and X_test is not None and not X_test.empty:
            test_preds = model.predict(X_test)
            test_evaluator = ModelEvaluator(y_test, test_preds).calculate_metrics()
        
        # 保存评估结果
        print("保存评估结果...")
        with open(os.path.join(route_dir, "evaluation.txt"), "w", encoding='utf-8') as f:
            f.write("==== 训练集评估 ====\n")
            f.write(train_evaluator.report("Train", return_str=True))
            
            if test_preds is not None:
                f.write("\n\n==== 测试集评估 ====\n")
                f.write(test_evaluator.report("Test", return_str=True))
        
        # 特征重要性
        print("生成特征重要性图...")
        if config["model_type"] == "lgb":
            lgb.plot_importance(model, max_num_features=20)
        else:
            xgb.plot_importance(model, max_num_features=20)
        plt.savefig(os.path.join(route_dir, "feature_importance.png"))
        plt.close()

        # 使用全部数据重新训练
        print("使用全部数据重新训练模型...")
        X_full, y_full, _, _, data_with_features_full = route_processor.prepare_data(
            origin=origin,
            destination=destination,
            test_size=0
        )
        model_full = get_model(config["time_granularity"], config["model_type"])
        model_full.fit(X_full, y_full)

        # 保存模型文件
        print("保存模型文件...")
        with open(os.path.join(route_dir, "model.pkl"), "wb") as f:
            pickle.dump(model_full, f)
        
        with open(os.path.join(route_dir, "preprocessor.pkl"), "wb") as f:
            pickle.dump(route_processor.preprocessor, f)
        
        with open(os.path.join(route_dir, "feature_builder.pkl"), "wb") as f:
            pickle.dump(route_processor.feature_builder, f)
        
        # 保存元数据
        metadata = {
            "feature_columns": X_train.columns.tolist(),
            "date_column": route_processor.date_col,
            "target_column": route_processor.target_col,
            "time_granularity": config["time_granularity"],
            "model_type": config["model_type"],
            "last_complete_date": data_with_features_full[route_processor.date_col].max().strftime('%Y-%m-%d'),
            "feature_count": len(X_train.columns),
            "training_samples": len(X_train),
            "test_samples": len(X_test) if X_test is not None else 0
        }
        with open(os.path.join(route_dir, "metadata.json"), "w", encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 保存最新数据
        latest_data = data_with_features_full.copy()
        latest_data.to_csv(os.path.join(route_dir, "latest_data.csv"), index=False)
        
        # 未来预测
        print("生成未来预测...")
        history = data_with_features.copy()
        feature_cols = X_train.columns.tolist()
        date_col = route_processor.date_col
        target_col = route_processor.target_col
        
        # 调整预测周期
        future_periods = config["future_periods"]
        if config["time_granularity"] == 'quarterly':
            future_periods = future_periods // 3
        elif config["time_granularity"] == 'yearly':
            future_periods = future_periods // 12
        
        latest_data = data_with_features_full.copy()
        last_complete_date = data_with_features_full[date_col].max()
        
        # 确保起始点正确
        if config["time_granularity"] == 'quarterly':
            while last_complete_date.month not in [3, 6, 9, 12]:
                last_complete_date -= pd.DateOffset(months=1)
        elif config["time_granularity"] == 'yearly':
            while last_complete_date.month != 12:
                last_complete_date -= pd.DateOffset(months=1)
        
        future_preds = []
        for i in range(future_periods):
            # 日期增量
            if config["time_granularity"] == 'monthly':
                offset = pd.DateOffset(months=1)
            elif config["time_granularity"] == 'quarterly':
                offset = pd.DateOffset(months=3)
            else:
                offset = pd.DateOffset(years=1)
            
            next_date = last_complete_date + offset
            next_row = {'YearMonth': next_date}
            latest_data = pd.concat([latest_data, pd.DataFrame([next_row])], ignore_index=True)
            latest_data = route_processor.preprocessor.fit_transform(latest_data)
            latest_data = route_processor.feature_builder.fit_transform(latest_data)
            latest_input = latest_data.iloc[[-1]][feature_cols]
            next_pred = model_full.predict(latest_input)[0]
            latest_data.loc[latest_data.index[-1], 'Route_Total_Seats'] = next_pred
            future_preds.append({'YearMonth': next_date, 'Predicted': next_pred})
            last_complete_date = next_date
        
        # 创建结果DataFrame
        train_df = pd.DataFrame({
            'YearMonth': history[date_col].iloc[:len(X_train)],
            'Actual': y_train,
            'Predicted': train_preds,
            'Set': 'Train'
        })
        
        test_df = pd.DataFrame()
        if test_preds is not None:
            test_df = pd.DataFrame({
                'YearMonth': history[date_col].iloc[len(X_train):len(X_train)+len(X_test)],
                'Actual': y_test,
                'Predicted': test_preds,
                'Set': 'Test'
            })
        
        future_df = pd.DataFrame(future_preds)
        future_df['Actual'] = np.nan
        future_df['Set'] = 'Future'
        
        result_df = pd.concat([train_df, test_df, future_df])
        result_df.to_csv(os.path.join(route_dir, "prediction_results.csv"), index=False)
        
        # 可视化结果
        if config["plot_results"]:
            print("生成预测结果图...")
            plt.figure(figsize=(14, 6))
            plt.plot(result_df['YearMonth'], result_df['Actual'], label='实际值', color='black')
            
            # 训练集预测
            train_mask = result_df['Set'] == 'Train'
            plt.plot(
                result_df[train_mask]['YearMonth'], 
                result_df[train_mask]['Predicted'], 
                label='训练集预测', linestyle='--', color='blue'
            )
            
            # 测试集预测
            if not test_df.empty:
                test_mask = result_df['Set'] == 'Test'
                plt.plot(
                    result_df[test_mask]['YearMonth'], 
                    result_df[test_mask]['Predicted'], 
                    label='测试集预测', linestyle='--', color='red', 
                    marker='o', markersize=3
                )
            
            # 未来预测
            future_mask = result_df['Set'] == 'Future'
            plt.plot(
                result_df[future_mask]['YearMonth'], 
                result_df[future_mask]['Predicted'], 
                label='未来预测', linestyle='--', color='green'
            )
            
            # 添加分割线
            if not test_df.empty:
                split_date = test_df['YearMonth'].min()
                plt.axvline(x=split_date, color='gray', linestyle=':', label='训练/测试分割线')
            
            plt.title(f"航线座位预测: {origin} → {destination}")
            plt.xlabel("日期")
            plt.ylabel("座位数")
            plt.legend()
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(route_dir, "forecast_plot.png"))
            plt.close()
        
        print(f"√ 航线 {origin}-{destination} 训练完成!")
        print(f"结果保存在: {route_dir}")
        
        # 返回成功状态和结果信息
        result_info = {
            "route_dir": route_dir,
            "training_samples": len(X_train),
            "test_samples": len(X_test) if X_test is not None else 0,
            "feature_count": len(X_train.columns),
            "train_metrics": train_evaluator.calculate_metrics(),
            "test_metrics": test_evaluator.calculate_metrics() if test_evaluator else None
        }
        
        return True, result_info
    
    except Exception as e:
        print(f"! 航线 {origin}-{destination} 训练失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, str(e)

# 使用示例
if __name__ == "__main__":
    # 示例1: 使用默认配置训练单条航线
    success, result = train_single_route("CAN", "PEK")
    
    if success:
        print("训练成功!")
        print(f"结果目录: {result['route_dir']}")
        print(f"训练样本数: {result['training_samples']}")
        print(f"特征数量: {result['feature_count']}")
    else:
        print(f"训练失败: {result}")
    
    # 示例2: 使用自定义配置
    custom_config = {
        "time_granularity": "monthly",
        "model_type": "xgb",
        "test_size": 6,
        "future_periods": 24,
        "base_save_dir": "./custom_results"
    }
    
    # success2, result2 = train_single_route("CAN", "PVG", custom_config)
