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
    path('forecast/models/', views.get_forecast_models, name='get_forecast_models'),
    path('forecast/run/', views.forecast_route_view, name='forecast_route_view'),
    path('pretrain/model/', views.pretrain_model_request, name='pretrain_model_request'),
    path('formal/train/', views.formal_train_model, name='formal_train_model'),
    path('pretrain/models/', views.get_pretrain_models, name='get_pretrain_models'),
    path('data/get_flightdata/', views.query_flight_market, name='query_flight_market'),
]