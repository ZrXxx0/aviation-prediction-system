#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
简单的测试脚本，验证导入和基本功能
"""

import os
import sys

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    # 测试导入
    print("测试导入...")
    from predict.models import PretrainRecord, RouteModelInfo
    print("✓ 模型导入成功")
    
    from predict.views import formal_train_model
    print("✓ 视图函数导入成功")
    
    print("\n所有导入测试通过！")
    
except ImportError as e:
    print(f"导入失败: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"其他错误: {e}")
    import traceback
    traceback.print_exc()
