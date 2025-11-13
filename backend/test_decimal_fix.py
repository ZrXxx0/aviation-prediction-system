#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：验证decimal.Decimal类型问题的修复
"""

import sys
import os
import pandas as pd
import numpy as np
from decimal import Decimal

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

# 模拟数据库数据（包含Decimal类型）
def create_test_data():
    """创建包含Decimal类型的测试数据"""
    data = {
        'YearMonth': ['2023-01', '2023-02', '2023-03', '2023-04', '2023-05'],
        'Route_Total_Seats': [Decimal('100.5'), Decimal('120.3'), Decimal('95.7'), Decimal('110.2'), Decimal('105.8')],
        'Route_Total_Flights': [Decimal('50.0'), Decimal('60.0'), Decimal('45.0'), Decimal('55.0'), Decimal('52.0')],
        'Distance (KM)': [Decimal('1200.5'), Decimal('1200.5'), Decimal('1200.5'), Decimal('1200.5'), Decimal('1200.5')]
    }
    return pd.DataFrame(data)

def test_numpy_operations():
    """测试numpy操作是否支持Decimal类型"""
    print("=== 测试numpy操作 ===")
    
    # 创建包含Decimal的数据
    df = create_test_data()
    print(f"原始数据类型: {df.dtypes}")
    
    # 测试np.average
    try:
        values = df['Route_Total_Seats'].iloc[-3:]
        weights = np.linspace(0.5, 1, 3)
        weights /= weights.sum()
        
        # 修复前（会报错）
        print("修复前测试...")
        result = np.average(values, weights=weights)
        print(f"np.average结果: {result}")
    except Exception as e:
        print(f"修复前报错: {e}")
        
        # 修复后
        print("修复后测试...")
        values_float = values.astype(float)
        result = np.average(values_float, weights=weights)
        print(f"np.average结果: {result}")
    
    # 测试时间序列模型
    try:
        print("\n测试时间序列模型...")
        from predictive_algorithm.FeatureEngineer import DataPreprocessor
        
        # 创建预处理器
        preprocessor = DataPreprocessor(
            time_col='YearMonth',
            fill_method='interp',
            max_invalid_ratio=0.5,
            normalize=False
        )
        
        # 转换数据
        result_df = preprocessor.transform(df)
        print(f"预处理后数据类型: {result_df.dtypes}")
        print("预处理成功！")
        
    except Exception as e:
        print(f"预处理失败: {e}")
        import traceback
        traceback.print_exc()

def test_data_conversion():
    """测试数据类型转换"""
    print("\n=== 测试数据类型转换 ===")
    
    df = create_test_data()
    
    # 测试pd.to_numeric
    for col in ['Route_Total_Seats', 'Route_Total_Flights', 'Distance (KM)']:
        try:
            converted = pd.to_numeric(df[col], errors='coerce')
            print(f"{col}: {df[col].dtype} -> {converted.dtype}")
        except Exception as e:
            print(f"{col} 转换失败: {e}")
    
    # 测试astype
    try:
        converted = df[['Route_Total_Seats', 'Route_Total_Flights']].astype(float)
        print(f"astype转换成功: {converted.dtypes}")
    except Exception as e:
        print(f"astype转换失败: {e}")

if __name__ == "__main__":
    print("开始测试decimal.Decimal类型问题修复...")
    
    test_data_conversion()
    test_numpy_operations()
    
    print("\n测试完成！")
