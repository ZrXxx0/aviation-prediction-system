from rest_framework import serializers
from .models import RouteMonthlyStat




class RouteMonthlyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteMonthlyStat
        fields = '__all__'