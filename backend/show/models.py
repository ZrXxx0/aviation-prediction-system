from django.db import models
# Create your models here.


# 航线月度统计
class RouteMonthlyStat(models.Model):
    origin_code = models.CharField(max_length=10, null=True, blank=True, help_text="出发机场三字码")
    destination_code = models.CharField(max_length=10, null=True, blank=True, help_text="到达机场三字码")

    year = models.IntegerField(help_text="年份")
    month = models.IntegerField(help_text="月份")


    passenger_volume = models.FloatField(null=True, blank=True,help_text="航线总客运量（万人次）")  # 运量
    Route_Total_Seats = models.FloatField(null=True, blank=True,help_text="航线总座位数（座位）")  # 运力
    Route_Total_Flights = models.IntegerField(null=True, blank=True,help_text="航线总航班数量（班次）")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("origin_code", "destination_code", "year", "month")
        ordering = ["-year", "-month"]
        verbose_name = "航线月度统计"
        verbose_name_plural = "航线月度统计"

    def __str__(self):
        return f"{self.origin_code} → {self.destination_code} - {self.year}-{self.month:02d}"

class AirportInfo(models.Model):
    code = models.CharField(max_length=3, unique=True)  # IATA 三字码唯一
    city = models.CharField(max_length=100)
    airport = models.CharField(max_length=200)
    province = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.city} - {self.airport} ({self.code})"