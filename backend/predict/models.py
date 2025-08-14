from django.db import models
from datetime import datetime
# from .model_registry.model_registry import get_model  # 临时注释，避免pandas导入问题
# Create your models here.

# 航线预测模型
class RouteModelInfo(models.Model):
    """
    航线预测模型元信息表（仅存路径，不做文件存储）：
    - 元文件（训练配置 JSON）
    - 模型文件
    - 原始数据文件（本次训练的原始切片）
    - 预处理器文件
    - 特征构建器文件
    - 评估指标：MAE / RMSE / MAPE / R^2（训练&测试）
    - 时间粒度：yearly / quarterly / monthly
    """
    GRANULARITY_CHOICES = [
        ("yearly", "年度"),
        ("quarterly", "季度"),
        ("monthly", "月度"),
    ]

    # 主键：起点_终点_YYYYMMDDHHMMSS
    model_id = models.CharField(max_length=64, primary_key=True, help_text="起点_终点_YYYYMMDDHHMMSS")

    # 航线（机场三字码）
    origin_airport = models.CharField(max_length=10, help_text="起点机场三字码")
    destination_airport = models.CharField(max_length=10, help_text="终点机场三字码")

    # 训练数据范围 & 粒度
    train_start_time = models.DateField(help_text="训练数据起始日期")
    train_end_time = models.DateField(help_text="训练数据结束日期")
    time_granularity = models.CharField(max_length=10, choices=GRANULARITY_CHOICES, help_text="时间粒度")

    # 训练元信息
    train_datetime = models.DateTimeField(help_text="模型训练完成时间")

    # ===== 五个文件地址（字符串路径）=====
    meta_file_path = models.CharField(max_length=512, help_text="元文件（训练配置 JSON）路径")
    model_file_path = models.CharField(max_length=512, help_text="模型文件路径")
    raw_data_file_path = models.CharField(max_length=512, help_text="原始数据文件路径")
    preprocessor_file_path = models.CharField(max_length=512, help_text="预处理器文件路径")
    feature_builder_file_path = models.CharField(max_length=512, help_text="特征构建器文件路径")

    # 训练集评估指标
    train_mae = models.FloatField(null=True, blank=True)
    train_rmse = models.FloatField(null=True, blank=True)
    train_mape = models.FloatField(null=True, blank=True)
    train_r2 = models.FloatField(null=True, blank=True)

    # 测试集评估指标
    test_mae = models.FloatField(null=True, blank=True)
    test_rmse = models.FloatField(null=True, blank=True)
    test_mape = models.FloatField(null=True, blank=True)
    test_r2 = models.FloatField(null=True, blank=True)

    remark = models.TextField(null=True, blank=True)   # 备注信息，可以记录模型的训练环境信息等
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "route_model_info"
        ordering = ["-train_datetime"]
        indexes = [
            models.Index(fields=["origin_airport", "destination_airport"]),
            models.Index(fields=["time_granularity"]),
            models.Index(fields=["train_start_time", "train_end_time"]),
        ]
        # 如需限制同一航线+粒度+时间范围唯一，可解开下行：
        # unique_together = ("origin_airport", "destination_airport", "time_granularity", "train_start_time", "train_end_time")

    def __str__(self):
        return f"{self.model_id} [{self.origin_airport}->{self.destination_airport}] {self.time_granularity}"

    @classmethod
    def generate_model_id(cls, origin_airport: str, destination_airport: str) -> str:
        """生成唯一模型ID：起点_终点_秒级时间戳（UTC）"""
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"{origin_airport}_{destination_airport}_{ts}"