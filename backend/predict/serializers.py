from rest_framework import serializers
import models

class MacroEconomicIndicatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MacroEconomicIndicator
        fields = '__all__'

class MLModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.MLModel
        fields = '__all__'

class PredictionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.PredictionRecord
        fields = '__all__'

class FlightStatRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FlightStatRecord
        fields = '__all__'

class RouteMonthlyStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.RouteMonthlyStat
        fields = '__all__'