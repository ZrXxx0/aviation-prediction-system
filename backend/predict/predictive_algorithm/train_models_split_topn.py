import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
import pandas as pd
import time
import random
from sklearn.linear_model import LinearRegression
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from concurrent.futures import ProcessPoolExecutor, as_completed
from statsmodels.tsa.arima.model import ARIMA
from .time_granularity import TimeGranularityController

from .TS_model import ARIMAModel
from .model_evaluation import ModelEvaluator
from .FeatureEngineer import DataPreprocessor, FeatureBuilder, AirlineRouteModel
from .create_model import get_model
from .filter_large_samples import filter_routes,double_filter_routes

import warnings
warnings.filterwarnings("ignore")



##################################    全局配置   ##################################
# 数据加载地址
current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/...
base_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'Predict_Datas')  # backend/Predict_Datas
ROUTE_DATA_REPORT_PATH = os.path.join(base_dir,'route_ranking.csv')
# 输出目录
BASE_SAVE_DIR = base_dir
# 全局参数配置
CONFIG = {
    "test_size": 4,  # 测试集大小
    "time_granularity": "monthly",  # 时间粒度
    "add_ts_forecast": True,  # 是否添加时间序列特征
    "future_periods": 20*12,  # 预测时长
    "max_workers": 18,  # 并行处理的最大进程数
    "model_type": "lgb",  # 'lgb' 或 'xgb'
    "plot_results": False,  # 是否生成结果图表
    "save_data": False,  # 是否保存中间数据
    "filter_mode": "top_n",  # 筛选方式: 'threshold'（阈值筛选）或 'top_n'（前n条筛选）
    "min_valid_ratio": None,  # 最小有效比例阈值（filter_mode='threshold'时使用）
    "top_n": 500,  # 前n条航线数量（filter_mode='top_n'时使用）
    "include_other": True,  # 是否处理剩余航线作为"其他"航线
    "max_lr_ratio":0.2
}

##################################    核心函数   ##################################
def get_last_valid_distance(route_data):
    """
    获取航线最后的有效距离（用于将预测的Seats转换为ASK）
    """
    if 'Distance (KM)' not in route_data.columns:
        return 0

    # 过滤掉0和空值
    valid_dist = route_data[route_data['Distance (KM)'] > 10]['Distance (KM)']

    if valid_dist.empty:
        return 0

    # 取最后一条记录的距离（假设近期距离最准）
    return valid_dist.iloc[-1]


def save_route_plot(history_df, future_df, save_path, title, y_col_hist, y_col_future, ylabel):
    """
    绘制并保存历史与预测的对比图
    """
    try:
        plt.figure(figsize=(12, 6))

        # 确保时间列是 datetime 格式
        history_dates = pd.to_datetime(history_df['YearMonth'])
        future_dates = pd.to_datetime(future_df['YearMonth'])

        # 绘制历史数据
        plt.plot(history_dates, history_df[y_col_hist], label='Historical Data', color='#1f77b4', linewidth=2)

        # 绘制预测数据
        plt.plot(future_dates, future_df[y_col_future], label='Forecast', color='#d62728', linestyle='--', linewidth=2)

        plt.title(title, fontsize=14)
        plt.xlabel('Date', fontsize=12)
        plt.ylabel(ylabel, fontsize=12)
        plt.legend()
        plt.grid(True, linestyle=':', alpha=0.6)

        # 优化X轴日期显示
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.gcf().autofmt_xdate()  # 自动旋转日期标签

        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
    except Exception as e:
        print(f"绘图失败: {e}")
        plt.close()


def ensure_dir_robust(dir_path, max_retries=5):
    if os.path.exists(dir_path):
        return True

    for i in range(max_retries):
        try:
            os.makedirs(dir_path, exist_ok=True)
            if os.path.exists(dir_path):
                return True
            time.sleep(0.01 * (i + 1))  # 极短的退避等待
        except OSError:
            time.sleep(0.05 + random.random() * 0.05)  # 随机等待防止再次碰撞

    # 最后尝试一次，如果还不行则报错
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path, exist_ok=True)
        except Exception as e:
            print(f"创建目录严重失败 {dir_path}: {e}")
            return False
    return True


def process_other_routes_simple(remaining_routes, domestic, config, save_dir):
    """
    处理剩余的小航线（Other-Other）：
    1. 计算每条航线每月的 ASK (Seats * Distance)
    2. 按时间加和得到总 ASK
    3. 使用 ARIMA 预测总 ASK 趋势
    """
    print("\n=== 开始处理剩余航线 (Other-Other) [Simple ARIMA Mode] ===")

    if remaining_routes.empty:
        print("没有剩余航线需要处理")
        return

    try:
        # 1. 筛选数据
        remaining_route_pairs = set(zip(remaining_routes['Origin'], remaining_routes['Destination']))

        # 使用 boolean mask 快速筛选
        mask = domestic.apply(lambda row: (row['Origin'], row['Destination']) in remaining_route_pairs, axis=1)
        other_data = domestic[mask].copy()

        if other_data.empty:
            print("警告: 剩余航线对应的数据集为空")
            return

        # 2. 计算 ASK (关键修改：先乘再加)
        # 确保距离和座位数是数值型
        other_data['Distance (KM)'] = pd.to_numeric(other_data['Distance (KM)'], errors='coerce').fillna(0)
        other_data['Route_Total_Seats'] = pd.to_numeric(other_data['Route_Total_Seats'], errors='coerce').fillna(0)

        # 计算单条记录的 ASK
        other_data['ASK'] = other_data['Route_Total_Seats'] * other_data['Distance (KM)']

        # 3. 按时间聚合
        # 转换时间列
        other_data['YearMonth'] = pd.to_datetime(other_data['YearMonth'])

        # 聚合得到时间序列
        ts_data = other_data.groupby('YearMonth')['ASK'].sum().sort_index()

        # 处理时间粒度 (重采样以确保时间连续)
        granularity = config["time_granularity"]
        freq_map = {'monthly': 'MS', 'quarterly': 'QS', 'yearly': 'YS'}
        freq = freq_map.get(granularity, 'MS')

        ts_data = ts_data.resample(freq).sum()  # 使用sum，因为ASK是累加量

        # 保存聚合后的历史数据
        route_dir = os.path.join(save_dir, "OTHER_OTHER")
        os.makedirs(route_dir, exist_ok=True)
        ts_data.to_csv(os.path.join(route_dir, "history_ask.csv"))

        # 4. ARIMA 预测
        print(f"拟合 ARIMA 模型，历史数据点数: {len(ts_data)}")

        # 1. 训练线性趋势模型
        ts_pre = ts_data.copy()

        trend_model = None
        has_trend = False

        if len(ts_pre) >= 12:  # 至少有一年数据才拟合趋势
            X_trend = np.array([t.toordinal() for t in ts_pre.index]).reshape(-1, 1)
            y_trend = ts_pre.values

            trend_model = LinearRegression()
            trend_model.fit(X_trend, y_trend)
            has_trend = True
            print(f"√ 成功拟合历史长期趋势 (R2: {trend_model.score(X_trend, y_trend):.4f})")
        else:
            print("! 历史数据不足，仅使用 ARIMA")

        # 简单的 ARIMA 参数，对于这种聚合趋势通常 (1,1,1) 或 (5,1,0) 即可
        # 这里使用 (1,1,0) 加 季节性 或简单自回归，为了稳健使用 (1,1,1)
        arima_model = ARIMA(ts_data, order=(1, 1, 1))
        arima_fit = arima_model.fit()

        # 计算预测步长
        future_periods = config["future_periods"]
        if granularity == 'quarterly':
            future_periods = future_periods // 3
        elif granularity == 'yearly':
            future_periods = future_periods // 12

        # 生成日期索引
        last_date = ts_data.index[-1]
        future_dates = []
        current_date = last_date

        for _ in range(future_periods):
            if granularity == 'monthly':
                current_date += pd.DateOffset(months=1)
            elif granularity == 'quarterly':
                current_date += pd.DateOffset(months=3)
            else:
                current_date += pd.DateOffset(years=1)
            future_dates.append(current_date)

        future_dates = pd.DatetimeIndex(future_dates)

        # 1. 获取 ARIMA 预测值
        arima_forecast = arima_fit.forecast(steps=future_periods)

        # 2. 计算融合预测值
        final_preds = []

        for i, date in enumerate(future_dates):
            # ARIMA 分量
            pred_arima = arima_forecast.iloc[i]

            final_val = pred_arima

            if has_trend:
                # 线性趋势 分量
                pred_trend = trend_model.predict([[date.toordinal()]])[0]

                # 动态权重计算 (Glide Path)
                # i=0 (近期) -> weight_trend = 0
                # i=end (远期) -> weight_trend = MAX_TREND_WEIGHT
                max_trend_weight = config['max_lr_ratio']
                weight_trend = (i / future_periods) * max_trend_weight
                weight_arima = 1.0 - weight_trend

                # 融合
                final_val = (pred_arima * weight_arima) + (pred_trend * weight_trend)

            # 确保不小于0
            final_preds.append(max(0, final_val))

        # 5. 格式化输出
        future_df = pd.DataFrame({
            'YearMonth': future_dates,
            'Predicted_ASK': final_preds
        })

        # 因为是对 ASK 直接建模，Route_Total_Seats 设为 NaN 或者 0 (因为没有单一的距离可以反推)
        future_df['Predicted_Seats'] = 0
        future_df['Distance'] = 0  # 混合距离无意义

        future_df.to_csv(os.path.join(route_dir, "future_predictions.csv"), index=False, encoding='utf-8-sig')

        history_df_for_plot = ts_data.reset_index()
        history_df_for_plot.columns = ['YearMonth', 'ASK']

        plot_path = os.path.join(route_dir, "forecast_plot.png")
        save_route_plot(
            history_df=history_df_for_plot,
            future_df=future_df,
            save_path=plot_path,
            title="Other-Other Routes Aggregated Forecast (ASK)",
            y_col_hist='ASK',
            y_col_future='Predicted_ASK',
            ylabel='Total ASK'
        )

        history_df_for_plot['Actual_Seats'] = 0
        history_df_for_plot['Distance'] = 0
        history_df_for_plot.rename(columns={'ASK': 'Actual_Seats'}, inplace=True)
        history_save_path = os.path.join(route_dir, "history_data.csv")
        history_df_for_plot.to_csv(history_save_path, index=False, encoding='utf-8-sig')

        print(f"√ 剩余航线聚合预测完成，已保存至 {route_dir}")

    except Exception as e:
        print(f"! 剩余航线处理失败: {str(e)}")
        import traceback
        traceback.print_exc()


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
        if hasattr(model, 'set_params'):
            model.set_params(n_jobs=1, verbose=-1)
        # 训练模型
        model.fit(X_train, y_train)
        
        # 评估模型
        train_preds = model.predict(X_train)
        train_evaluator = ModelEvaluator(y_train, train_preds)  # 先实例化
        train_evaluator.calculate_metrics()  # 计算指标(如果该方法更新内部状态)
        
        test_preds = None
        test_evaluator = None
        if config["time_granularity"] != 'yearly' and X_test is not None and not X_test.empty:
            test_preds = model.predict(X_test)
            test_evaluator = ModelEvaluator(y_test, test_preds)
            test_evaluator.calculate_metrics()
        
        # 保存评估结果
        with open(os.path.join(route_dir, "evaluation.txt"), "w", encoding='utf-8') as f:
            f.write("==== 训练集评估 ====\n")
            f.write(train_evaluator.report("Train", return_str=True))
            
            if test_preds is not None:
                f.write("\n\n==== 测试集评估 ====\n")
                f.write(test_evaluator.report("Test", return_str=True))

        # 使用全部可用数据（训练集+测试集）重新训练模型用于未来预测
        X_full, y_full, _, _, data_with_features_full = route_processor.prepare_data(
            origin=origin,
            destination=destination,
            test_size=0
        )
        # 使用相同的配置创建新模型
        model_full = get_model(config["time_granularity"], config["model_type"])
        if hasattr(model_full, 'set_params'):
            model_full.set_params(n_jobs=1, verbose=-1)
        model_full.fit(X_full, y_full)

        trend_model = None
        has_trend_model = False
        trend_data = data_with_features_full.copy()
        
        # 2. 只有当历史数据足够长(例如至少12个点)才训练趋势模型，否则只用机器学习模型
        if len(trend_data) >= 12:
            try:
                # 使用时间戳的 ordinal 作为特征 (简单的线性时间趋势 y = kt + b)
                X_trend = trend_data[route_processor.date_col].map(pd.Timestamp.toordinal).values.reshape(-1, 1)
                y_trend = trend_data['Route_Total_Seats'].values

                trend_model = LinearRegression()
                trend_model.fit(X_trend, y_trend)
                has_trend_model = True
                print(f"  -> 已训练历史趋势模型 (样本数: {len(trend_data)})")
            except Exception as e:
                print(f"  -> 趋势模型训练失败: {e}")
        else:
            print(f"  ->历史数据不足 ({len(trend_data)}条)，跳过趋势修正")
        # 未来预测
        feature_cols = X_train.columns.tolist()
        date_col = route_processor.date_col
        
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
        raw_route_data = route_processor.get_route_data(origin, destination)
        ref_distance = get_last_valid_distance(raw_route_data)
        history_df = data_with_features_full[['YearMonth', 'Route_Total_Seats']].copy()
        history_df.rename(columns={'Route_Total_Seats': 'Actual_Seats'}, inplace=True)

        history_df['Distance'] = ref_distance
        history_df['Actual_ASK'] = history_df['Actual_Seats'] * ref_distance
        history_save_path = os.path.join(route_dir, "history_data.csv")
        history_df.to_csv(history_save_path, index=False, encoding='utf-8-sig')

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

            # 1. 机器学习模型预测 (ML Prediction)
            ml_pred = model_full.predict(latest_input)[0]

            # 2. 融合逻辑
            final_pred = ml_pred
            if has_trend_model:
                # 计算趋势预测 (Trend Prediction)
                next_date_ordinal = np.array([[next_date.toordinal()]])
                trend_pred = trend_model.predict(next_date_ordinal)[0]

                # 计算动态权重 (Dynamic Weighting)
                # 策略:
                # i=0 (近期) -> weight_trend 接近 0, 主要靠 ML 模型
                # i=future_periods (远期) -> weight_trend 接近 0.8 或 1.0, 主要靠趋势

                max_trend_weight = config['max_lr_ratio']

                # 线性增长权重: 从 0 增长到 max_trend_weight
                weight_trend = (i / future_periods) * max_trend_weight
                weight_ml = 1.0 - weight_trend

                # 融合
                final_pred = (ml_pred * weight_ml) + (trend_pred * weight_trend)

            # 确保非负
            next_pred_seats = max(0, final_pred)

            # 将融合后的预测值填回 latest_data，这样下一轮的 lag 特征会基于融合后的结果
            latest_data.loc[latest_data.index[-1], 'Route_Total_Seats'] = next_pred_seats

            pred_ask = next_pred_seats * ref_distance

            future_preds.append({
                'YearMonth': next_date,
                'Predicted_Seats': next_pred_seats,
                'Distance': ref_distance,
                'Predicted_ASK': pred_ask
            })
            last_complete_date = next_date
        
        # 创建未来预测DataFrame
        future_predictions_df = pd.DataFrame(future_preds)
        if not future_predictions_df.empty:
            # os.makedirs(route_dir, exist_ok=True)
            future_predictions_df.to_csv(os.path.join(route_dir, "future_predictions.csv"), index=False,
                                         encoding='utf-8-sig')
            plot_path = os.path.join(route_dir, "forecast_plot.png")
            save_route_plot(
                history_df=data_with_features_full,
                future_df=future_predictions_df,
                save_path=plot_path,
                title=f"{origin} -> {destination} Forecast (Seats)",
                y_col_hist='Route_Total_Seats',
                y_col_future='Predicted_Seats',
                ylabel='Seats'
            )

        print(f"√ 航线 {origin}-{destination} 处理完成")
        return True
    
    except Exception as e:
        print(f"! 航线 {origin}-{destination} 处理失败: {str(e)}")
        return False


def process_all_routes(domestic, config):
    """
    主流程控制器
    """
    print("加载航线列表...")
    if not os.path.exists(ROUTE_DATA_REPORT_PATH):
        print("! 航线报告文件不存在")
        return

    # 1. 筛选航线
    top_n = config.get("top_n", 500)

    valid_routes, remaining_routes = double_filter_routes(
        report_path=ROUTE_DATA_REPORT_PATH,
        top_n=top_n
    )

    routes_list = list(valid_routes[['Origin', 'Destination']].itertuples(index=False, name=None))

    print(f"筛选出 {len(valid_routes)} 条主要航线进行详细建模")
    print(f"剩余 {len(remaining_routes)} 条小航线将进行聚合预测")

    # 创建保存目录
    base_dir = os.path.join(BASE_SAVE_DIR, f"{config['time_granularity']}_{config['model_type']}")
    config["base_save_dir"] = base_dir
    ensure_dir_robust(base_dir)

    # 保存配置和列表
    valid_routes.to_csv(os.path.join(base_dir, "valid_routes.csv"), index=False)
    pd.Series(config).to_csv(os.path.join(base_dir, "config.csv"))

    # 2. 处理 Top N 航线 (并行)
    print("\n>>> 阶段 1: 处理 Top N 主要航线 <<<")

    success_count = 0

    with ProcessPoolExecutor(max_workers=config["max_workers"]) as executor:
        futures = {}
        for route in routes_list:
            origin, destination = route

            # 提取数据
            mask = (domestic['Origin'] == origin) & (domestic['Destination'] == destination)
            route_data = domestic[mask].copy()

            futures[executor.submit(process_single_route, route, route_data, config)] = route

        print(f"提交任务: {len(futures)} ")

        for future in as_completed(futures):
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                print(f"Task error: {e}")

    # 3. 处理剩余航线 (单线程聚合处理)
    if config["include_other"] and not remaining_routes.empty:
        print("\n>>> 阶段 2: 处理 Other 剩余航线 (ASK 聚合模式) <<<")
        process_other_routes_simple(remaining_routes, domestic, config, base_dir)

    print(f"\n全部完成! 结果保存在: {base_dir}")

##################################    执行处理   ##################################
if __name__ == "__main__":
    # 加载数据
    print("加载数据集...")
    # DOMESTIC_DATA_PATH = '.'
    # domestic = pd.read_csv(DOMESTIC_DATA_PATH, low_memory=False)
    #
    # # 执行批量处理
    # process_all_routes(domestic, CONFIG)