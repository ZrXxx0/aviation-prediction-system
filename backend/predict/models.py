from typing import Optional

from django.db import models
from datetime import datetime
from django.utils import timezone
from django.db import models, IntegrityError, transaction
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

    # 外键关联预训练记录
    pretrain_record = models.ForeignKey(
        "PretrainRecord",
        on_delete=models.SET_NULL,  # 删除 PretrainRecord 时设为 NULL
        null=True,  # 数据库层面允许 NULL
        blank=True,  # 表单/管理后台允许留空
        related_name="route_models",
        help_text="来源的预训练记录"
    )

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

# 航线市场数据表
class FlightMarketRecord(models.Model):
    year_month = models.CharField(max_length=20, verbose_name="YearMonth")  # 统计周期（如 Jan-11 / 2011-01），字符串形式存
    origin = models.CharField(max_length=10, verbose_name="Origin")  # 起点机场三字码
    destination = models.CharField(max_length=10, verbose_name="Destination")  # 终点机场三字码
    equipment = models.CharField(max_length=10, verbose_name="Equipment")  # 机型/设备代码（如 73G/CRJ 等）
    distance_km = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Distance (KM)", null=True, blank=True)  # 航段距离（公里）
    international_flight = models.BooleanField(default=False, verbose_name="International Flight")  # 是否国际航班（原始值 0/1，导入时映射为 False/True）

    equipment_total_flights = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Equipment_Total_Flights", null=True, blank=True)  # 该机型执飞的总航班数
    equipment_total_seats = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Equipment_Total_Seats", null=True, blank=True)  # 该机型提供的总座位数
    route_total_flights = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Route_Total_Flights", null=True, blank=True)  # 该航线总航班数
    route_total_seats = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Route_Total_Seats", null=True, blank=True)  # 该航线总座位数
    route_total_flight_time = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Route_Total_Flight_Time", null=True, blank=True)  # 航线累计飞行时长（单位依数据源：小时/分钟）
    route_avg_flight_time = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Route_Avg_Flight_Time", null=True, blank=True)  # 单班平均飞行时长（单位依数据源）

    con_total_est_pax = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Con Total Est. Pax", null=True, blank=True)  # 估算“转机（Connecting）旅客”总量
    first = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="First", null=True, blank=True)  # 估算头等舱旅客数/份额（依数据源定义）
    business = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Business", null=True, blank=True)  # 估算商务舱旅客数/份额
    premium = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Premium", null=True, blank=True)  # 估算高端经济/高端舱旅客数/份额
    full_y = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Full Y", null=True, blank=True)  # 估算全价经济舱（Y 舱全价）旅客数/份额
    disc_y = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Disc Y", null=True, blank=True)  # 估算折扣经济舱（Y 舱折扣）旅客数/份额

    avg_yield = models.DecimalField(max_digits=12, decimal_places=4, verbose_name="Avg yield", null=True, blank=True)  # 平均客公里收益/收益率（Yield，单位依数据源）
    avg_first = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Avg First", null=True, blank=True)  # 头等舱平均票价/收益
    avg_business = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Avg Business", null=True, blank=True)  # 商务舱平均票价/收益
    avg_premium = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Avg Premium", null=True, blank=True)  # 高端经济/高端舱平均票价/收益
    avg_full_y = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Avg Full Y", null=True, blank=True)  # 全价经济舱平均票价/收益
    avg_disc_y = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Avg Disc Y", null=True, blank=True)  # 折扣经济舱平均票价/收益

    region = models.CharField(max_length=50, verbose_name="Region", null=True, blank=True)  # 区域/大区（如国内某区、国际分区）

    total_est_pax = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Total Est. Pax", null=True, blank=True)  # 估算总旅客量（O&D+联程）
    local_est_pax = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Local Est. Pax", null=True, blank=True)  # 估算本地（O&D）旅客量（直达起讫）
    behind_est_pax = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Behind Est. Pax", null=True, blank=True)  # 估算 Behind 旅客（从起点之前出发，经起点联程）
    bridge_est_pax = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Bridge Est. Pax", null=True, blank=True)  # 估算 Bridge 旅客（双向/跨枢纽联程，桥接型）
    beyond_est_pax = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Beyond Est. Pax", null=True, blank=True)  # 估算 Beyond 旅客（到达终点后继续联程至后续目的地）

    avg_fare_usd = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Avg Fare (USD)", null=True, blank=True)  # 平均票价（美元）
    local_fare = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Local Fare", null=True, blank=True)  # 本地（O&D）平均票价
    behind_fare = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Behind Fare", null=True, blank=True)  # Behind 旅客平均票价
    bridge_fare = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Bridge Fare", null=True, blank=True)  # Bridge 旅客平均票价
    beyond_fare = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Beyond Fare", null=True, blank=True)  # Beyond 旅客平均票价

    o_gdp = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="O_GDP", null=True, blank=True)  # 起点城市/地区 GDP（单位依数据源）
    o_population = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="O_Population", null=True, blank=True)  # 起点人口规模（单位依数据源：万人/人）
    third_industry_x = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Third_Industry_x", null=True, blank=True)  # 起点第三产业指标（x 版/口径）
    o_revenue = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="O_Revenue", null=True, blank=True)  # 起点财政收入/营业收入指标
    o_retail = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="O_Retail", null=True, blank=True)  # 起点社会消费品零售总额
    o_labor = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="O_Labor", null=True, blank=True)  # 起点劳动/就业规模指标
    o_air_traffic = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="O_Air_Traffic", null=True, blank=True)  # 起点航空吞吐量/客运量指标

    d_gdp = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="D_GDP", null=True, blank=True)  # 终点城市/地区 GDP
    d_population = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="D_Population", null=True, blank=True)  # 终点人口规模
    third_industry_y = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="Third_Industry_y", null=True, blank=True)  # 终点第三产业指标（y 版/口径）
    d_revenue = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True, verbose_name="D_Revenue")  # 终点财政收入/营业收入指标
    d_retail = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="D_Retail", null=True, blank=True)  # 终点社会消费品零售总额
    d_labor = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="D_Labor", null=True, blank=True)  # 终点劳动/就业规模指标
    d_air_traffic = models.DecimalField(max_digits=14, decimal_places=2, verbose_name="D_Air_Traffic", null=True, blank=True)  # 终点航空吞吐量/客运量指标

    created_at = models.DateTimeField(auto_now_add=True)  # 记录创建时间（技术字段）
    updated_at = models.DateTimeField(auto_now=True)  # 记录更新时间（技术字段）

    class Meta:
        verbose_name = "航线市场统计记录"
        verbose_name_plural = "航线市场统计记录"
        indexes = [
            models.Index(fields=["origin", "destination", "year_month"]),  # 常用查询索引：起终点+周期
        ]
        unique_together = (("origin", "destination", "equipment",  "year_month"),)  # 同一周期/机型/航线唯一

    def __str__(self):
        return f"{self.year_month} {self.origin}-{self.destination} {self.equipment}"


# 预训练记录表
class PretrainRecord(models.Model):
    GRANULARITY_CHOICES = [
        ("yearly", "年度"),
        ("quarterly", "季度"),
        ("monthly", "月度"),
    ]
    id = models.AutoField(primary_key=True, verbose_name="ID")  # 自增主键
    origin = models.CharField(max_length=10, verbose_name="起点")
    destination = models.CharField(max_length=10, verbose_name="终点")

    meta_file_path = models.CharField(max_length=512, help_text="元文件（训练配置 JSON）路径")

    # 训练数据范围 & 粒度（起止为“日期”）
    train_start_date = models.DateField(verbose_name="训练数据起始日期")
    train_end_date   = models.DateField(verbose_name="训练数据结束日期")
    time_granularity = models.CharField(
        max_length=10,
        choices=GRANULARITY_CHOICES,
        default="monthly",
        verbose_name="时间粒度",
        help_text="时间粒度（与步长单位一致）",
    )

    # 步长（整数；与时间粒度配合：如 monthly + 3 = 每3个月一步）
    step_size = models.IntegerField(
        null=True, blank=True,
        verbose_name="步长",
        help_text="滑动/取样步长，整数；单位与时间粒度一致"
    )

    # 训练元信息：完成时间 & 耗时
    train_datetime = models.DateTimeField(verbose_name="模型训练完成时间")
    train_duration = models.DurationField(null=True, blank=True, verbose_name="训练耗时")  # timedelta

    # 训练集评估指标
    train_mae  = models.FloatField(null=True, blank=True)
    train_rmse = models.FloatField(null=True, blank=True)
    train_mape = models.FloatField(null=True, blank=True)
    train_r2   = models.FloatField(null=True, blank=True)

    # 测试集评估指标
    test_mae  = models.FloatField(null=True, blank=True)
    test_rmse = models.FloatField(null=True, blank=True)
    test_mape = models.FloatField(null=True, blank=True)
    test_r2   = models.FloatField(null=True, blank=True)

    # 预训练模型报告 PDF 地址
    report_pdf = models.CharField(max_length=512, verbose_name="报告PDF地址", null=True, blank=True)

    # 审计字段
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    # 训练结果：成功/失败
    success = models.BooleanField(default=True, verbose_name="训练是否成功")
    # 是否采用预训练模型
    use_pretrain = models.BooleanField(
        default=False,
        verbose_name="是否采用该预训练模型",
        help_text="标记该航线预测模型是否基于预训练模型"
    )


    class Meta:
        verbose_name = "预训练记录"
        verbose_name_plural = "预训练记录"
        indexes = [
            models.Index(fields=["origin", "destination"]),
            models.Index(fields=["time_granularity"]),
            models.Index(fields=["train_start_date", "train_end_date"]),
            models.Index(fields=["train_datetime"]),
        ]

    def __str__(self):
        return f"{self.origin}-{self.destination} [{self.time_granularity}] @ {self.train_datetime:%Y-%m-%d %H:%M}"
