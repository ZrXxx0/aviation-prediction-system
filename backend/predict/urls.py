"""
URL configuration for AirlinePredictSystem project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
    path('macro-indicator/', views.macro_indicator_view, name='macro_indicator'),
    path('macro-indicator-trend/', views.macro_indicator_trend_view, name='macro_indicator_trend'),
    path('flight-statistics/', views.flight_statistics_view, name='flight_statistics'),
    path('prediction-records/', views.prediction_record_list, name='prediction_records'),
    path('route-stat-query/', views.route_stat_query, name='route_stat_query'),
    path('route-stat-yearly/', views.route_stat_yearly_total, name='route_stat_yearly'),
    path('route-stat-recent/', views.route_stat_recent_12_months, name='route_stat_recent'),
]