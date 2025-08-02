from django.db import models
# from .model_registry.model_registry import get_model  # 临时注释，避免pandas导入问题
# Create your models here.

# 城市经济信息
class MacroEconomicIndicator(models.Model):
    city = models.CharField(max_length=50, help_text="城市名称")
    city_code = models.CharField(max_length=10, help_text="三字码", null=True, blank=True)
    province = models.CharField(max_length=50, help_text="所属省份")
    period = models.DateField(help_text="统计周期（年月）")  # 比如 2024-07-01
    gdp = models.FloatField(help_text="GDP（亿元）")
    population = models.FloatField(help_text="人口（万人）")
    tertiary_industry_ratio = models.FloatField(help_text="第三产业占比（%）")
    income_per_capita = models.FloatField(help_text="人均可支配收入（元）")
    retail_total = models.FloatField(help_text="社会消费品零售总额（万元）")
    employment_total = models.FloatField(help_text="三产业就业人数总和（万人）")
    air_passenger_volume = models.FloatField(help_text="民用航空客运量（万人）")

    class Meta:
        unique_together = ("city", "period")
        ordering = ["-period"]

    def __str__(self):
        return f"{self.city} - {self.period}"


# 预测模型类
class MLModel(models.Model):
    MODEL_TYPE_CHOICES = [
        ("lgb", "LightGBM"),
        ("xgb", "XGBoost"),
    ]
    GRANULARITY_CHOICES = [
        ("monthly", "月度"),
        ("quarterly", "季度"),
        ("yearly", "年度"),
    ]

    name = models.CharField(max_length=10, choices=MODEL_TYPE_CHOICES)
    granularity = models.CharField(max_length=10, choices=GRANULARITY_CHOICES)
    parameters = models.JSONField(help_text="模型超参数配置")  # 这个逻辑需要打磨，是不是支持我们再手动输入超参数

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("name", "granularity", "parameters")

    def build_sklearn_model(self):
        # 临时注释，避免pandas导入问题
        # model = get_model(self.granularity, self.name)
        # model.set_params(**self.parameters)
        # return model
        raise NotImplementedError("模型构建功能暂时不可用，需要解决pandas依赖问题")

    def __str__(self):
        return f"{self.name}-{self.granularity}"



# 预测记录类
class PredictionRecord(models.Model):
    origin = models.CharField(max_length=50, help_text="出发城市")
    destination = models.CharField(max_length=50, help_text="到达城市")
    origin_code = models.CharField(max_length=10)  # 出发城市字节码
    destination_code = models.CharField(max_length=10)  # 到达城市字节码
    period_type = models.CharField(max_length=10, choices=[("monthly", "月度"), ("quarterly", "季度"), ("yearly", "年度")])
    prediction_date = models.DateField()  # 本次预测生成的时间
    period_start = models.DateField()  # 预测数据起始时间
    period_end = models.DateField()  # 预测数据结束时间

    # 结果保存为文件路径（如 /media/predictions/xxx.csv）
    result_file = models.FileField(upload_to="predictions/", null=True, blank=True)

    model = models.ForeignKey(
        "MLModel",
        on_delete=models.PROTECT,
        related_name="predictions",
        help_text="使用的预测模型"
    )
    features_summary = models.JSONField(null=True, blank=True)  # 特征描述,比如：关键影响因素权重

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "origin",
            "destination",
            "period_type",
            "period_start",
            "period_end",
            "model",
        )
        ordering = ["-prediction_date"]

    def __str__(self):
        return f"{self.origin}-{self.destination} {self.period_type} {self.period_start}"


# 航线运量统计记录
class FlightStatRecord(models.Model):
    origin = models.CharField(max_length=50, help_text="出发城市")
    destination = models.CharField(max_length=50, help_text="到达城市")
    aircraft_type = models.CharField(max_length=50, help_text="机型")  # 如 A320
    period = models.DateField(help_text="统计周期（年月）")  # 比如 2024-07-01
    period_type = models.CharField(max_length=10, choices=[("monthly", "月度"), ("quarterly", "季度"), ("yearly", "年度")])

    actual_volume = models.FloatField(help_text="实际客运量（人次）")
    available_capacity = models.FloatField(help_text="可用运力（座位数）")
    flights = models.IntegerField(help_text="航班频次")
    load_factor = models.FloatField(help_text="客座率")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("origin", "destination", "aircraft_type", "period", "period_type")
        ordering = ["-period"]
        verbose_name = "航线运量记录"
        verbose_name_plural = "航线运量记录（所有）"

    def __str__(self):
        return f"{self.origin}-{self.destination} @ {self.period.strftime('%Y-%m')} {self.aircraft_type}"
