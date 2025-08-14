import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
import matplotlib.pyplot as plt
from concurrent.futures import ProcessPoolExecutor, as_completed
from time_granularity import TimeGranularityController
from sklearn.linear_model import LinearRegression
from TS_model import ARIMAModel
from model_evaluation import ModelEvaluator
from FeatureEngineer import DataPreprocessor, FeatureBuilder, AirlineRouteModel
from create_model import get_model
from filter_large_samples import filter_routes

import warnings
warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体
plt.rcParams['axes.unicode_minus'] = False



##################################    全局配置   ##################################
# 数据加载地址
ROUTE_DATA_REPORT_PATH = './route_data_report.csv'
DOMESTIC_DATA_PATH = './final_data_0622.csv'
# 输出目录
BASE_SAVE_DIR = './results'
# 全局参数配置
CONFIG = {
    "test_size": 12,  # 测试集大小
    "time_granularity": "monthly",  # 时间粒度
    "add_ts_forecast": True,  # 是否添加时间序列特征
    "future_periods": 36,  # 预测时长
    "max_workers": 2,  # 并行处理的最大进程数
    "model_type": "lgb",  # 'lgb' 或 'xgb'
    "plot_results": True,  # 是否生成结果图表
    "save_data": True,  # 是否保存中间数据
    "min_valid_ratio": 0.8,  # 最小有效比例阈值
    "return_result": True,  # 确保函数返回 result_df
    "reconcile_mode": True  # 标志是否进行层级对齐流程
}

##################################    核心函数   ##################################
def process_single_route(route, domestic, config):
    """
    处理单条航线的完整流程
    :param route: 元组 (origin, destination)
    :param domestic: 数据集
    :param config: 配置字典
    :return: 处理状态 (成功/失败)
    """
    origin, destination = route
    print(f"\n=== 开始处理航线: {origin} -> {destination} ===")
    
    try:
        # 创建航线专属目录
        route_dir = os.path.join(
            config["base_save_dir"], 
            f"{origin}_{destination}"
        )
        os.makedirs(route_dir, exist_ok=True)
        
        # 初始化预处理组件
        preprocessor = DataPreprocessor(
            fill_method='interp',
            normalize=False,
            non_economic_tail_window=6,
        )
        
        # 初始化时间粒度控制器
        granularity_controller = TimeGranularityController(config["time_granularity"])
        
        # 初始化时间序列模型
        ts_model = ARIMAModel(
            order=(1,1,1),
            freq=granularity_controller.get_freq()
        )
        
        # 初始化特征工程
        feature_builder = FeatureBuilder(
            granularity_controller=granularity_controller,
            add_ts_forecast=config["add_ts_forecast"],
            ts_model=ts_model
        )
        
        # 初始化航线处理器
        route_processor = AirlineRouteModel(
            data=domestic,
            preprocessor=preprocessor,
            feature_builder=feature_builder,
            granularity=config["time_granularity"]
        )
        
        # 准备数据
        X_train, y_train, X_test, y_test, data_with_features = route_processor.prepare_data(
            origin=origin,
            destination=destination,
            test_size=config["test_size"]
        )
        
        # 检查数据是否有效
        if X_train is None or X_train.empty:
            print(f"! 航线 {origin}-{destination} 数据不足，跳过处理")
            return False
        
        # 保存数据
        if config["save_data"]:
            X_train.to_csv(os.path.join(route_dir, "X_train.csv"), index=False)
            X_test.to_csv(os.path.join(route_dir, "X_test.csv"), index=False)
            pd.DataFrame(y_train).to_csv(os.path.join(route_dir, "y_train.csv"), index=False)
            pd.DataFrame(y_test).to_csv(os.path.join(route_dir, "y_test.csv"), index=False)
            data_with_features.to_csv(os.path.join(route_dir, "data_with_features.csv"), index=False)
        
        # 初始化模型
        model = get_model(config["time_granularity"], config["model_type"])
        # 训练模型
        model.fit(X_train, y_train)
        
        # 评估模型
        train_preds = model.predict(X_train)
        train_evaluator = ModelEvaluator(y_train, train_preds).calculate_metrics()
        
        test_preds = None
        if config["time_granularity"] != 'yearly' and X_test is not None and not X_test.empty:
            test_preds = model.predict(X_test)
            test_evaluator = ModelEvaluator(y_test, test_preds).calculate_metrics()
        
        # 保存评估结果
        with open(os.path.join(route_dir, "evaluation.txt"), "w", encoding='utf-8') as f:
            f.write("==== 训练集评估 ====\n")
            f.write(train_evaluator.report("Train", return_str=True))
            
            if test_preds is not None:
                f.write("\n\n==== 测试集评估 ====\n")
                f.write(test_evaluator.report("Test", return_str=True))
        
        # 特征重要性
        if config["model_type"] == "lgb":
            lgb.plot_importance(model, max_num_features=20)
        else:
            xgb.plot_importance(model, max_num_features=20)
        plt.savefig(os.path.join(route_dir, "feature_importance.png"))
        plt.close()
        
        # 未来预测
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
        
        latest_data = data_with_features.copy()
        last_complete_date = data_with_features[date_col].max()
        
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
            next_pred = model.predict(latest_input)[0]
            latest_data.loc[latest_data.index[-1], 'Route_Total_Seats'] = next_pred
            future_preds.append({'YearMonth': next_date, 'Predicted': next_pred})
            last_complete_date = next_date
        
        # 保存最新数据
        if config["save_data"]:
            latest_data.to_csv(os.path.join(route_dir, "latest_data.csv"), index=False)
        
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
        
        print(f"√ 航线 {origin}-{destination} 处理完成")
        # === 返回结果 ===
        if config.get("return_result", False):
            return result_df  # 用于后续对齐或可视化
        else:
            return True  # 用于普通并行任务时统计成功数量


    except Exception as e:
        print(f"! 航线 {origin}-{destination} 处理失败: {str(e)}")
        return False

# 线性回归对齐（Linear Reconciliation）
def linear_reconcile_monthly_to_quarterly(result_monthly, result_quarterly):
    """
    将月度预测结果按季度总量进行层级对齐，返回对齐后的 result_monthly。
    """
    # 添加季度列
    result_monthly['quarter'] = pd.to_datetime(result_monthly['YearMonth']).dt.to_period('Q').dt.to_timestamp()
    result_quarterly['quarter'] = pd.to_datetime(result_quarterly['YearMonth']).dt.to_period('Q').dt.to_timestamp()

    # 聚合月度预测为季度总量
    monthly_q = result_monthly.groupby('quarter')['Predicted'].sum().reset_index(name='monthly_sum')
    quarterly_q = result_quarterly[['quarter', 'Predicted']].rename(columns={'Predicted': 'quarterly_sum'})

    # 合并季度对齐数据
    merged_q = pd.merge(monthly_q, quarterly_q, on='quarter', how='inner')

    if merged_q.empty:
        print("⚠️ 层级对齐失败：无匹配的季度数据")
        result_monthly['Predicted_Reconciled'] = result_monthly['Predicted']
        return result_monthly

    # 线性回归校准
    reg = LinearRegression().fit(merged_q[['monthly_sum']], merged_q['quarterly_sum'])
    monthly_q['adjusted'] = reg.predict(monthly_q[['monthly_sum']])

    # 映射回原始月度数据
    result_monthly = pd.merge(result_monthly, monthly_q[['quarter', 'monthly_sum', 'adjusted']], on='quarter', how='left')
    result_monthly['adjust_ratio'] = result_monthly['adjusted'] / result_monthly['monthly_sum']

    # 只对测试集和未来预测值进行调整
    result_monthly['Predicted_Reconciled'] = result_monthly.apply(
        lambda row: row['Predicted'] * row['adjust_ratio']
        if row['Set'] in ['Test', 'Future'] else row['Predicted'], axis=1
    )

    return result_monthly

def plot_forecast(df, title, y_col='Predicted', actual_col='Actual'):
    """
    可视化预测结果（支持对齐后预测值）。
    :param df: 包含 YearMonth, Set, Actual, y_col 等字段的数据
    :param title: 图标题
    :param y_col: 预测列名，默认是 'Predicted'，可设为 'Predicted_Reconciled'
    :param actual_col: 实际值列名
    """

    plt.figure(figsize=(14, 6))
    plt.plot(df['YearMonth'], df[actual_col], label='Actual', color='black')

    # 训练集预测
    train_mask = df['Set'] == 'Train'
    plt.plot(df[train_mask]['YearMonth'], df[train_mask][y_col],
             label='Train Pred', linestyle='--', color='blue')

    # 测试集预测
    test_mask = df['Set'] == 'Test'
    if not df[test_mask].empty:
        plt.plot(df[test_mask]['YearMonth'], df[test_mask][y_col],
                 label='Test Pred', linestyle='--', color='red', marker='o')

    # 未来预测
    future_mask = df['Set'] == 'Future'
    if not df[future_mask].empty:
        plt.plot(df[future_mask]['YearMonth'], df[future_mask][y_col],
                 label='Future Forecast', linestyle='--', color='green')

    # 分割线
    if not df[test_mask].empty:
        split_date = df[test_mask]['YearMonth'].min()
        plt.axvline(x=split_date, color='gray', linestyle=':', label='Train/Test Split')

    plt.title(title)
    plt.xlabel("Date")
    plt.ylabel("Seats")
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()
def process_and_reconcile_route(route, domestic, base_config):
    """
    处理航线的月度与季度预测，执行层级对齐，并可视化
    """
    origin, destination = route
    print(f"\n=== 层级对齐处理: {origin} → {destination} ===")

    try:
        # === 配置月度预测 ===
        config_monthly = base_config.copy()
        config_monthly["time_granularity"] = "monthly"
        config_monthly["return_result"] = True
        config_monthly["plot_results"] = False

        # === 配置季度预测 ===
        config_quarterly = base_config.copy()
        config_quarterly["time_granularity"] = "quarterly"
        config_quarterly["return_result"] = True
        config_quarterly["plot_results"] = False

        # === 调用两次预测 ===
        result_m = process_single_route(route, domestic.copy(), config_monthly)
        result_q = process_single_route(route, domestic.copy(), config_quarterly)

        if result_m is None or result_q is None:
            print(f"❌ 层级对齐失败: {origin}-{destination}")
            return False

        # === 对齐预测 ===
        reconciled = linear_reconcile_monthly_to_quarterly(result_m, result_q)

        # === 保存 + 可视化 ===
        base_dir = base_config.get("base_save_dir", "./results")
        save_dir = os.path.join(base_dir, "reconciled")
        os.makedirs(save_dir, exist_ok=True)

        reconciled.to_csv(os.path.join(save_dir, f"{origin}_{destination}_monthly_reconciled.csv"), index=False)
        result_q.to_csv(os.path.join(save_dir, f"{origin}_{destination}_quarterly.csv"), index=False)

        plot_forecast(reconciled, f"月度预测（对齐后）: {origin} → {destination}", y_col="Predicted_Reconciled")
        plot_forecast(result_q, f"季度预测: {origin} → {destination}")

        print(f"√ 层级对齐完成: {origin}-{destination}")
        return True

    except Exception as e:
        print(f"❌ 层级对齐异常 {origin}-{destination}: {e}")
        return False

def process_all_routes(domestic, config):
    """
    处理所有航线
    :param domestic: 数据集
    :param config: 配置字典
    """
    # 从文件加载航线列表
    print("加载航线列表...")
    if not os.path.exists(ROUTE_DATA_REPORT_PATH):
        print("! 航线报告文件不存在")
        return
    route_report = pd.read_csv(ROUTE_DATA_REPORT_PATH)
    
    # 过滤有效比例大于阈值的航线
    min_ratio = config["min_valid_ratio"]
    valid_routes = filter_routes(min_ratio,ROUTE_DATA_REPORT_PATH)
    
    # 创建航线元组列表
    routes_list = list(valid_routes[['Origin', 'Destination']].itertuples(index=False, name=None))
    
    print(f"找到 {len(route_report)} 条航线")
    print(f"有效比例 > {min_ratio} 的航线: {len(valid_routes)} 条")
    print(f"时间粒度: {config['time_granularity']}")
    print(f"使用模型: {config['model_type']}")
    print(f"并行进程: {config['max_workers']}")
    
    # 创建基础保存目录
    base_dir = os.path.join(
        BASE_SAVE_DIR, 
        f"{config['time_granularity']}_{config['model_type']}"
    )
    config["base_save_dir"] = base_dir
    os.makedirs(base_dir, exist_ok=True)
    
    # 保存筛选后的航线列表
    valid_routes.to_csv(os.path.join(base_dir, "valid_routes.csv"), index=False)
    
    # 保存配置
    pd.Series(config).to_csv(os.path.join(base_dir, "config.csv"))
    
    # 并行处理航线
    success_count = 0
    with ProcessPoolExecutor(max_workers=config["max_workers"]) as executor:
        futures = {
            executor.submit(
                process_and_reconcile_route,
                route, 
                domestic.copy(),  # 避免数据共享问题
                config
            ): route for route in routes_list
        }
        
        for future in as_completed(futures):
            route = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                print(f"处理航线 {route} 时出错: {str(e)}")
    
    print(f"\n处理完成! 成功处理 {success_count}/{len(routes_list)} 条航线")
    print(f"结果保存在: {base_dir}")

##################################    执行处理   ##################################
if __name__ == "__main__":
    # 加载数据
    print("加载数据集...")
    domestic = pd.read_csv(DOMESTIC_DATA_PATH, low_memory=False)
    process_all_routes(domestic, CONFIG)