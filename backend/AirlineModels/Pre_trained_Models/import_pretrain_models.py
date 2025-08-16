
import os
import django
from typing import Optional
from contextlib import nullcontext
from django.db import transaction

# 1) 设置 Django 环境（改成你的 settings 模块）
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AirlinePredictSystem.settings")
django.setup()

from predict.models import RouteModelInfo, PretrainRecord


def migrate_route_to_pretrain(step_size: int = 1, dry_run: bool = False) -> None:
    """
    把 RouteModelInfo 的记录导入到 PretrainRecord，并回填外键到 RouteModelInfo.pretrain_record

    :param step_size: 给新建的 PretrainRecord 设定步长（若你的表允许为空，也可传 None）
    :param dry_run:   只打印，不写库
    """
    qs = RouteModelInfo.objects.all().order_by("train_datetime")
    total = qs.count()
    print(f"[INFO] Found {total} RouteModelInfo rows.")

    created_cnt = 0
    linked_cnt = 0

    ctx = nullcontext() if dry_run else transaction.atomic()
    with ctx:
        for r in qs:
            # 2) 在 PretrainRecord 中按关键字段 get_or_create（幂等）
            pr, created = PretrainRecord.objects.get_or_create(
                origin=r.origin_airport,
                destination=r.destination_airport,
                meta_file_path=r.meta_file_path,
                train_start_date=r.train_start_time,   # RouteModelInfo 中是 DateField（命名 *_time）
                train_end_date=r.train_end_time,
                time_granularity=r.time_granularity,
                train_datetime=r.train_datetime,
                defaults={
                    "step_size": step_size,
                    "train_duration": None,
                    # 指标从 RouteModelInfo 同步过来
                    "train_mae": r.train_mae,
                    "train_rmse": r.train_rmse,
                    "train_mape": r.train_mape,
                    "train_r2": r.train_r2,
                    "test_mae": r.test_mae,
                    "test_rmse": r.test_rmse,
                    "test_mape": r.test_mape,
                    "test_r2": r.test_r2,
                    # 你的 PretrainRecord 里没有原生 report_pdf 来源，这里留空
                    "report_pdf": None,
                    # 你模型里有 success / use_pretrain 字段，这里给个默认值
                    "success": True,
                    "use_pretrain": True,
                }
            )
            if created:
                created_cnt += 1
                print(f"[CREATE] PretrainRecord id={pr.id} for {r.origin_airport}-{r.destination_airport} @ {r.train_datetime}")

            # 3) 回填外键到 RouteModelInfo（允许为空，直接赋值）
            if r.pretrain_record_id != getattr(pr, "id", None):
                r.pretrain_record = pr
                if not dry_run:
                    r.save(update_fields=["pretrain_record"])
                linked_cnt += 1
                print(f"[LINK] RouteModelInfo {r.model_id} -> PretrainRecord id={pr.id}")

    print(f"[DONE] Created: {created_cnt}, Linked: {linked_cnt}, Total scanned: {total}")


if __name__ == "__main__":
    # 示例：正常迁移（写库）
    migrate_route_to_pretrain(step_size=12, dry_run=False)

    # 如果只想看看会做什么而不写库：
    # migrate_route_to_pretrain(step_size=1, dry_run=True)
