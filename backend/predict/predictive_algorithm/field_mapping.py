#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库字段名到CSV列名的映射配置
"""

# 数据库字段名 -> CSV列名映射
FIELD_TO_CSV_MAPPING = {
    'year_month': 'YearMonth',
    'origin': 'Origin',
    'destination': 'Destination',
    'equipment': 'Equipment',
    'distance_km': 'Distance (KM)',
    'international_flight': 'International Flight',
    'equipment_total_flights': 'Equipment_Total_Flights',
    'equipment_total_seats': 'Equipment_Total_Seats',
    'route_total_flights': 'Route_Total_Flights',
    'route_total_seats': 'Route_Total_Seats',
    'route_total_flight_time': 'Route_Total_Flight_Time',
    'route_avg_flight_time': 'Route_Avg_Flight_Time',
    'con_total_est_pax': 'Con Total Est. Pax',
    'first': 'First',
    'business': 'Business',
    'premium': 'Premium',
    'full_y': 'Full Y',
    'disc_y': 'Disc Y',
    'avg_yield': 'Avg yield',
    'avg_first': 'Avg First',
    'avg_business': 'Avg Business',
    'avg_premium': 'Avg Premium',
    'avg_full_y': 'Avg Full Y',
    'avg_disc_y': 'Avg Disc Y',
    'region': 'Region',
    'total_est_pax': 'Total Est. Pax',
    'local_est_pax': 'Local Est. Pax',
    'behind_est_pax': 'Behind Est. Pax',
    'bridge_est_pax': 'Bridge Est. Pax',
    'beyond_est_pax': 'Beyond Est. Pax',
    'avg_fare_usd': 'Avg Fare (USD)',
    'local_fare': 'Local Fare',
    'behind_fare': 'Behind Fare',
    'bridge_fare': 'Bridge Fare',
    'beyond_fare': 'Beyond Fare',
    'o_gdp': 'O_GDP',
    'o_population': 'O_Population',
    'third_industry_x': 'Third_Industry_x',
    'o_revenue': 'O_Revenue',
    'o_retail': 'O_Retail',
    'o_labor': 'O_Labor',
    'o_air_traffic': 'O_Air_Traffic',
    'd_gdp': 'D_GDP',
    'd_population': 'D_Population',
    'third_industry_y': 'Third_Industry_y',
    'd_revenue': 'D_Revenue',
    'd_retail': 'D_Retail',
    'd_labor': 'D_Labor',
    'd_air_traffic': 'D_Air_Traffic',
}

# CSV列名 -> 数据库字段名映射（反向映射）
CSV_TO_FIELD_MAPPING = {v: k for k, v in FIELD_TO_CSV_MAPPING.items()}

# 需要特殊处理的字段
SPECIAL_FIELDS = {
    'international_flight': {
        'type': 'boolean_to_int',
        'description': '将True/False转换为1/0'
    }
}

def get_field_mapping():
    """获取字段映射配置"""
    return FIELD_TO_CSV_MAPPING.copy()

def get_csv_mapping():
    """获取CSV列名映射配置"""
    return CSV_TO_FIELD_MAPPING.copy()

def get_special_fields():
    """获取需要特殊处理的字段配置"""
    return SPECIAL_FIELDS.copy()
