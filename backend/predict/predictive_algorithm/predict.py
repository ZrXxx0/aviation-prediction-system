import os, json, joblib
import pandas as pd
import numpy as np

def forecast_from_files(
    meta_file_path: str,
    model_file_path: str,
    raw_data_file_path: str,
    preprocessor_file_path: str,
    feature_builder_file_path: str,
    showTrain: bool,
    numFeatures: int,
    save_data: bool = True,
):
    """
    使用已保存的五个文件进行“未来滚动预测”，不重新训练。
    - showTrain: 是否包含历史 Train/Test
    - numFeatures: 预测的时间点数（按模型粒度计）
    - save_data: 是否保存预测结果 CSV 到模型目录
    """
    # --- 0) 路径检查 ---
    for p in (meta_file_path, model_file_path, raw_data_file_path,
              preprocessor_file_path, feature_builder_file_path):
        if not os.path.isfile(p):
            raise FileNotFoundError(p)
    model_dir = os.path.dirname(model_file_path)

    # --- 1) 加载元信息和工件 ---
    with open(meta_file_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    date_col     = meta.get("date_column", "YearMonth")
    target_col   = meta.get("target_column", "Route_Total_Seats")
    feature_cols = meta.get("feature_columns")
    granularity  = meta.get("time_granularity") or "monthly"

    model           = joblib.load(model_file_path)
    preprocessor    = joblib.load(preprocessor_file_path)
    feature_builder = joblib.load(feature_builder_file_path)

    # --- 2) 准备历史数据 ---
    base_df = pd.read_csv(raw_data_file_path, low_memory=False)
    base_df.columns = (base_df.columns.astype(str).str.strip().str.replace('\ufeff', '', regex=True))

    if date_col != "YearMonth" and date_col in base_df.columns:
        base_df.rename(columns={date_col: "YearMonth"}, inplace=True)
        date_col = "YearMonth"

    # 转换日期
    s = pd.to_datetime(base_df[date_col], errors="coerce", format="%Y/%m/%d")
    mask = s.isna()
    if mask.any():
        s[mask] = pd.to_datetime(base_df.loc[mask, date_col], errors="coerce")
    base_df[date_col] = s.dt.to_period("M").dt.to_timestamp()

    if base_df[date_col].isna().any():
        raise ValueError(f"{date_col} 中存在无法解析的日期，请检查原始数据。")

    hist_tmp = preprocessor.fit_transform(base_df.copy())
    hist_tmp[date_col] = pd.to_datetime(hist_tmp[date_col], errors="coerce")
    hist_tmp[date_col] = hist_tmp[date_col].dt.to_period("M").dt.to_timestamp()
    hist_tmp = feature_builder.fit_transform(hist_tmp)

    if feature_cols is None:
        feature_cols = [c for c in hist_tmp.columns if c not in [date_col, target_col]]

    # --- 3) 预测起点 ---
    last_complete_date = pd.to_datetime(hist_tmp[date_col].max())
    if granularity == "quarterly":
        while last_complete_date.month not in (1, 4, 7, 10):
            last_complete_date -= pd.DateOffset(months=1)
        step = pd.DateOffset(months=3)
        next_date = last_complete_date + step
    elif granularity == "yearly":
        while last_complete_date.month != 1:
            last_complete_date -= pd.DateOffset(months=1)
        step = pd.DateOffset(years=1)
        next_date = last_complete_date + step
    else:
        step = pd.DateOffset(months=1)
        next_date = last_complete_date + step

    steps = max(0, int(numFeatures))

    # --- 4) 滚动预测 ---
    latest_data = base_df.copy()
    future_rows = []
    for _ in range(steps):
        latest_data = pd.concat([latest_data, pd.DataFrame([{date_col: next_date}])], ignore_index=True)
        tmp = preprocessor.fit_transform(latest_data.copy())
        tmp = feature_builder.fit_transform(tmp)
        x = tmp.iloc[[-1]][feature_cols]
        yhat = float(model.predict(x)[0])
        latest_data.loc[latest_data.index[-1], target_col] = yhat
        future_rows.append({date_col: next_date, "Predicted": yhat, "Actual": np.nan, "Set": "Future"})
        next_date = next_date + step

    future_df = pd.DataFrame(future_rows)
    if date_col != "YearMonth" and date_col in future_df.columns:
        future_df.rename(columns={date_col: "YearMonth"}, inplace=True)

    # --- 5) 合并历史预测 ---
    result_df = future_df
    if showTrain:
        # 基于当前数据重新生成 train/test
        split_index = len(hist_tmp) - meta.get("test_samples", 0)
        train_df = pd.DataFrame({
            "YearMonth": hist_tmp[date_col].iloc[:split_index],
            "Actual": base_df[target_col].iloc[:split_index],
            "Predicted": model.predict(hist_tmp[feature_cols].iloc[:split_index]),
            "Set": "Train"
        })
        test_df = pd.DataFrame({
            "YearMonth": hist_tmp[date_col].iloc[split_index:],
            "Actual": base_df[target_col].iloc[split_index:],
            "Predicted": model.predict(hist_tmp[feature_cols].iloc[split_index:]),
            "Set": "Test"
        })
        result_df = pd.concat([train_df, test_df, future_df], ignore_index=True)

    # --- 6) 保存结果 ---
    if save_data:
        out_path = os.path.join(model_dir, f"prediction_results_{numFeatures}.csv")
        result_df.to_csv(out_path, index=False)

    return result_df


# 直接运行这个文件可本地测试
if __name__ == "__main__":
    # 换成你的真实路径
    meta_path    = r"D:\desk\project\backend\AirlineModels\monthly_lgb\CAN_PEK_20250813233020\metadata.json"
    model_path   = r"D:\desk\project\backend\AirlineModels\monthly_lgb\CAN_PEK_20250813233020\model.pkl"
    raw_path     = r"D:\desk\project\backend\AirlineModels\monthly_lgb\CAN_PEK_20250813233020\latest_data.csv"
    preproc_path = r"D:\desk\project\backend\AirlineModels\monthly_lgb\CAN_PEK_20250813233020\preprocessor.pkl"
    feat_path    = r"D:\desk\project\backend\AirlineModels\monthly_lgb\CAN_PEK_20250813233020\feature_builder.pkl"

    df = forecast_from_files(
        meta_file_path=meta_path,
        model_file_path=model_path,
        raw_data_file_path=raw_path,
        preprocessor_file_path=preproc_path,
        feature_builder_file_path=feat_path,
        showTrain=True,     # 返回 Train/Test/Future
        numFeatures=12,     # 月度=12个月；季度=12个季度；年度=12年
        save_data=True
    )
    print("tail:\n", df.tail())
