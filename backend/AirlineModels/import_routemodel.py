# -*- coding: utf-8 -*-
"""
导入 AirlineModels 模型目录下的元数据、文件路径和评估指标到数据库表 RouteModelInfo
"""

import os
import re
import json
import sys
import argparse
from datetime import datetime

import pandas as pd
from django.db import transaction
from django.utils.timezone import make_aware

# ========= Django 初始化 =========
PROJECT_ROOT = r"D:\desk\project\backend"  # 项目根目录（manage.py 所在）
sys.path.append(PROJECT_ROOT)

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AirlinePredictSystem.settings")  # 改成你的 settings 模块
django.setup()

from predict.models import RouteModelInfo  # 改成你的 app 名

# ========= 配置 =========
# 顶层目录名 → time_granularity 字段值
GRANULARITY_DIR_MAP = {
    "monthly_lgb": "monthly",
    "quarterly_lgb": "quarterly",
    "yearly_lgb": "yearly",
}


# ========= 工具函数 =========
def parse_model_id(folder_name: str):
    """
    根据模型文件夹名解析出模型的起点、终点机场代码和训练完成时间
    期望文件夹名格式: ORG_DEST_YYYYmmddHHMMSS
    :param folder_name: 模型文件夹名
    :return: (origin_airport, destination_airport, train_datetime[带时区])
    """
    parts = folder_name.split("_")
    if len(parts) < 3:
        raise ValueError(f"非法 model_id: {folder_name}")
    origin, dest = parts[0], parts[1]
    ts = parts[2][:14]  # 截取到秒
    dt = datetime.strptime(ts, "%Y%m%d%H%M%S")
    return origin, dest, make_aware(dt)


def pick_raw_file(dir_path: str):
    """
    选择原始数据文件（优先 latest_data.csv，其次 data_with_features.csv）
    :param dir_path: 模型文件夹路径
    :return: 文件的绝对路径，如果都不存在则返回 None
    """
    for name in ("latest_data.csv", "data_with_features.csv"):
        p = os.path.join(dir_path, name)
        if os.path.isfile(p):
            return p
    return None


def parse_evaluation_txt(path: str):
    """
    从 evaluation.txt 文件解析训练集和测试集的 MAE / RMSE / MAPE / R^2 指标
    兼容中英文、大小写、以及 R²（上标 ²）
    :param path: evaluation.txt 路径
    :return: dict，格式：
             {
                 "train": {"mae":..., "rmse":..., "mape":..., "r2":...},
                 "test":  {...}
             }
    """
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()

    def get_block(keywords):
        pattern = r"(?:^|\n)\s*.*(" + "|".join(keywords) + r").*?\n(.*?)(?=\n\s*====|\Z)"
        m = re.search(pattern, txt, flags=re.S | re.I | re.U)
        return m.group(2) if m else ""

    train_block = get_block(["训练", "Train"])
    test_block = get_block(["测试", "Test"])

    def pick_metrics(block):
        num = r"([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)"
        out = {}
        patterns = {
            "rmse": [r"RMSE[:：]\s*" + num],
            "mae":  [r"MAE[:：]\s*" + num],
            "mape": [r"MAPE[:：]\s*" + num],
            # 关键：支持 R^2 / R2 / R-square / R²（上标 ²）
            "r2":   [
                r"R(?:\^?2|²)[:：]\s*" + num,
                r"R-?square[:：]\s*" + num,
            ],
        }
        for key, pats in patterns.items():
            val = None
            for p in pats:
                m = re.search(p, block, flags=re.I | re.U)
                if m:
                    try:
                        val = float(m.group(1))
                    except Exception:
                        val = None
                    break
            out[key] = val
        return out

    return {"train": pick_metrics(train_block), "test": pick_metrics(test_block)}


def infer_train_range_from_raw(raw_path: str, meta_date_col: str = None, last_complete_date: str = None):
    """
    从原始数据文件（如 latest_data.csv）推断训练数据的起止日期
    逻辑：
        - 确定日期列（优先 metadata.json 的 date_column，其次 YearMonth，再次包含 'date' 的列；
          否则自动选择“能解析出最多日期”的列）
        - 找到最小和最大日期
        - 如果有 last_complete_date，则最大值不超过它
    :param raw_path: 原始数据文件路径
    :param meta_date_col: 元文件中指定的日期列名（优先使用）
    :param last_complete_date: 元文件中指定的最后完整日期（可选）
    :return: (start_date, end_date, date_column_name)
    """
    if not raw_path or not os.path.isfile(raw_path):
        return None, None, None

    df = pd.read_csv(raw_path)

    def choose_date_col(df):
        if meta_date_col and meta_date_col in df.columns:
            return meta_date_col
        if "YearMonth" in df.columns:
            return "YearMonth"
        cand = [c for c in df.columns if "date" in str(c).lower()]
        if cand:
            return cand[0]
        best_col, best_count = None, -1
        for c in df.columns:
            try:
                parsed = pd.to_datetime(df[c], errors="coerce")
                cnt = parsed.notna().sum()
                if cnt > best_count:
                    best_col, best_count = c, cnt
            except Exception:
                continue
        return best_col

    date_col = choose_date_col(df)
    if not date_col:
        return None, None, None

    s = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if s.empty:
        return None, None, date_col

    if last_complete_date:
        try:
            lcd = pd.to_datetime(last_complete_date)
            s = s[s <= lcd]
        except Exception:
            pass

    if s.empty:
        return None, None, date_col

    return s.min().date(), s.max().date(), date_col


def relpath_under_base(path: str, base_dir: str) -> str:
    """
    把绝对路径转成相对 AirlineModels 根目录的路径，并统一使用 /
    :param path: 绝对路径
    :param base_dir: AirlineModels 根目录
    :return: 相对路径（使用 /）
    """
    try:
        return os.path.relpath(path, base_dir).replace("\\", "/")
    except Exception:
        return path.replace("\\", "/")


# ========= 主逻辑 =========
def run_import(base_dir: str, dry_run: bool = False):
    """
    扫描 AirlineModels 目录，读取各模型的元数据、指标和文件路径，入库到 RouteModelInfo
    :param base_dir: AirlineModels 根目录路径
    :param dry_run: 是否只打印不入库
    """
    if not os.path.isdir(base_dir):
        raise SystemExit(f"未找到目录: {base_dir}")

    created, updated = 0, 0

    with transaction.atomic():
        for gran_dir in os.listdir(base_dir):
            gran_path = os.path.join(base_dir, gran_dir)
            if not os.path.isdir(gran_path):
                continue

            time_granularity = GRANULARITY_DIR_MAP.get(gran_dir)
            if not time_granularity:
                continue

            for model_id in os.listdir(gran_path):
                model_dir = os.path.join(gran_path, model_id)
                if not os.path.isdir(model_dir):
                    continue

                try:
                    origin, dest, train_dt = parse_model_id(model_id)
                except Exception as e:
                    print(f"[跳过] {model_id}: {e}")
                    continue

                # 路径集中定义
                meta_path    = os.path.join(model_dir, "metadata.json")
                model_path   = os.path.join(model_dir, "model.pkl")
                preproc_path = os.path.join(model_dir, "preprocessor.pkl")
                feat_path    = os.path.join(model_dir, "feature_builder.pkl")
                raw_path     = pick_raw_file(model_dir)

                # 统一缺失检查
                missing = [name for name, p in [
                    ("metadata.json", meta_path),
                    ("model.pkl", model_path),
                    ("preprocessor.pkl", preproc_path),
                    ("feature_builder.pkl", feat_path),
                ] if not os.path.isfile(p)]
                if not raw_path:
                    missing.append("raw_data(csv)")
                if missing:
                    print(f"[跳过] {model_id} 缺少文件: {', '.join(missing)}")
                    continue

                # 指标：evaluation.txt
                metrics = {"train": {}, "test": {}}
                eval_path = os.path.join(model_dir, "evaluation.txt")
                if os.path.isfile(eval_path):
                    try:
                        metrics = parse_evaluation_txt(eval_path)
                    except Exception as e:
                        print(f"[警告] 解析 evaluation.txt 失败 {model_id}: {e}")
                else:
                    print(f"[警告] 缺少 evaluation.txt，将不写指标: {model_id}")

                # 从 meta 中取日期列名、最后完整日期
                date_col_in_meta = None
                last_complete_date = None
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    date_col_in_meta = meta.get("date_column")
                    last_complete_date = meta.get("last_complete_date")
                except Exception:
                    pass

                # 从原始数据获取训练起止时间
                train_start, train_end, _ = infer_train_range_from_raw(
                    raw_path,
                    meta_date_col=date_col_in_meta,
                    last_complete_date=last_complete_date,
                )

                # 将 5 个文件路径转换为相对 base_dir 的路径
                meta_rel    = relpath_under_base(meta_path, base_dir)
                model_rel   = relpath_under_base(model_path, base_dir)
                raw_rel     = relpath_under_base(raw_path, base_dir)
                preproc_rel = relpath_under_base(preproc_path, base_dir)
                feat_rel    = relpath_under_base(feat_path, base_dir)

                fields = dict(
                    model_id=model_id,
                    origin_airport=origin,
                    destination_airport=dest,
                    train_start_time=train_start,
                    train_end_time=train_end,
                    time_granularity=time_granularity,
                    train_datetime=train_dt,
                    # 五个文件（相对路径）
                    meta_file_path=meta_rel,
                    model_file_path=model_rel,
                    raw_data_file_path=raw_rel,
                    preprocessor_file_path=preproc_rel,
                    feature_builder_file_path=feat_rel,
                    # 指标
                    train_mae=metrics["train"].get("mae"),
                    train_rmse=metrics["train"].get("rmse"),
                    train_mape=metrics["train"].get("mape"),
                    train_r2=metrics["train"].get("r2"),
                    test_mae=metrics["test"].get("mae"),
                    test_rmse=metrics["test"].get("rmse"),
                    test_mape=metrics["test"].get("mape"),
                    test_r2=metrics["test"].get("r2"),
                    remark=f"{gran_dir} imported (from evaluation.txt)",
                )

                if dry_run:
                    print(f"[DRY] {model_id} -> {fields}")
                    continue

                obj, was_created = RouteModelInfo.objects.update_or_create(
                    model_id=model_id, defaults=fields
                )
                if was_created:
                    created += 1
                    print(f"[新增] {model_id}")
                else:
                    updated += 1
                    print(f"[更新] {model_id}")

    print(f"完成：新增 {created} 条，更新 {updated} 条")


# ========= 入口 =========
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入 AirlineModels 到 RouteModelInfo")
    parser.add_argument("--base", type=str, default=os.path.join(PROJECT_ROOT, "AirlineModels"),
                        help="AirlineModels 根目录")
    parser.add_argument("--dry-run", action="store_true", help="只打印不入库")
    args = parser.parse_args()

    run_import(args.base, dry_run=args.dry_run)
