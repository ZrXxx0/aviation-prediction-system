import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import xgboost as xgb
import matplotlib.pyplot as plt
import json
from datetime import datetime, timedelta
import time
import platform
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .time_granularity import TimeGranularityController
from .TS_model import ARIMAModel
from .model_evaluation import ModelEvaluator
from .FeatureEngineer import DataPreprocessor, FeatureBuilder, AirlineRouteModel
from .create_model import get_model, get_default_config, merge_model_params
from .field_mapping import get_field_mapping, get_special_fields

# Django相关导入
import django
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AirlinePredictSystem.settings')
django.setup()

from predict.models import FlightMarketRecord

import warnings

warnings.filterwarnings("ignore")

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False


def register_chinese_font():
    """
    Register Chinese font, prioritize font files in project assets folder
    """
    try:
        # Get current file directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Font file path in project assets folder
        project_font_path = os.path.join(current_dir, 'assets', 'simsunb.ttf')
        print(project_font_path)

        # Font path priority: project assets > system fonts
        font_paths = [project_font_path]

        # Add system fonts as alternatives
        system = platform.system()

        if system == "Windows":
            font_paths.extend([
                "C:/Windows/Fonts/simsun.ttc",  # SimSun
                "C:/Windows/Fonts/simhei.ttf",  # SimHei
                "C:/Windows/Fonts/msyh.ttc",  # Microsoft YaHei
                "C:/Windows/Fonts/simkai.ttf",  # SimKai
            ])
        elif system == "Darwin":  # macOS
            font_paths.extend([
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/Library/Fonts/Arial Unicode MS.ttf",
            ])
        else:  # Linux
            font_paths.extend([
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            ])

        # Try to register fonts
        registered_font = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    # Use different font names to avoid conflicts
                    font_name = 'ChineseFont_' + os.path.basename(font_path).replace('.', '_')
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    print(f"Successfully registered Chinese font: {font_path} with name: {font_name}")
                    registered_font = True
                    break  # Exit after successful registration
                except Exception as e:
                    print(f"Failed to register font {font_path}: {e}")
                    continue

        # If all fonts fail to register, use default font
        if not registered_font:
            print("Warning: No available Chinese fonts found, using default font")
            # Try to use built-in fonts
            try:
                # Use built-in Chinese font
                from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
                print("Using built-in STSong-Light font")
            except:
                print("Cannot use built-in Chinese font, will use Helvetica")

        return registered_font

    except Exception as e:
        print(f"Font registration process error: {e}")
        return False


def create_chinese_style(style_name, parent_style, font_name='Helvetica', **kwargs):
    """
    Create Chinese-supported style
    """
    styles = getSampleStyleSheet()

    # Try to use registered Chinese fonts
    try:
        # Check if there are registered Chinese fonts
        if 'ChineseFont' in pdfmetrics.getRegisteredFontNames():
            font_name = 'ChineseFont'
    except:
        pass

    # Create style
    style = ParagraphStyle(
        style_name,
        parent=styles[parent_style],
        fontName=font_name,
        **kwargs
    )

    return style


def generate_model_report(route_dir, origin, destination, time_granularity, model_type,
                          train_metrics, test_metrics, training_samples, test_samples,
                          feature_count, train_start_date, train_end_date, train_duration):
    """
    Generate model training report PDF

    :param route_dir: Model save directory
    :param origin: Origin airport code
    :param destination: Destination airport code
    :param time_granularity: Time granularity
    :param model_type: Model type
    :param train_metrics: Training set evaluation metrics
    :param test_metrics: Test set evaluation metrics
    :param training_samples: Training set sample count
    :param test_samples: Test set sample count
    :param feature_count: Feature count
    :param train_start_date: Training data start date
    :param train_end_date: Training data end date
    :param train_duration: Training duration
    :return: PDF file path
    """
    try:
        # Register Chinese font
        register_chinese_font()

        # Create PDF filename
        pdf_filename = f"model_report_{origin}_{destination}_{time_granularity}_{model_type}.pdf"
        pdf_path = os.path.join(route_dir, pdf_filename)

        # Create PDF document
        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        story = []

        # Get styles
        styles = getSampleStyleSheet()

        # Create Chinese-supported styles
        title_style = create_chinese_style(
            'CustomTitle',
            'Heading1',
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center
            textColor=colors.HexColor('#2E4057')  # Dark blue
        )

        heading_style = create_chinese_style(
            'CustomHeading',
            'Heading2',
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#2E86AB')  # Blue
        )

        normal_style = create_chinese_style(
            'CustomNormal',
            'Normal',
            fontSize=12,
            textColor=colors.HexColor('#4A4A4A')  # Dark gray
        )

        # Title
        story.append(Paragraph(f"Airline Prediction Model Training Report", title_style))
        story.append(Spacer(1, 20))

        # Basic information
        story.append(Paragraph("Basic Information", heading_style))
        basic_info = [
            ["Route", f"{origin} → {destination}"],
            ["Time Granularity", time_granularity],
            ["Model Type", model_type.upper()],
            ["Training Data Start Date", train_start_date.strftime('%Y-%m-%d')],
            ["Training Data End Date", train_end_date.strftime('%Y-%m-%d')],
            ["Training Duration", str(train_duration)],
            ["Feature Count", str(feature_count)],
            ["Training Samples", str(training_samples)],
            ["Test Samples", str(test_samples)]
        ]

        # Style the table
        basic_table = Table(basic_info, colWidths=[2 * inch, 3 * inch])
        basic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),  # Blue header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),  # Use Helvetica to avoid Chinese issues
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),  # Light gray background
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8F9FA')]),  # Alternating row background
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D1D1'))  # Light gray grid
        ]))
        story.append(basic_table)
        story.append(Spacer(1, 20))

        # Training set evaluation metrics
        story.append(Paragraph("Training Set Evaluation Metrics", heading_style))
        if train_metrics:
            train_data = [
                ["Metric", "Value"],
                ["MAE (Mean Absolute Error)", f"{train_metrics.get('mae', 'N/A'):.4f}"],
                ["RMSE (Root Mean Square Error)", f"{train_metrics.get('rmse', 'N/A'):.4f}"],
                ["MAPE (Mean Absolute Percentage Error)", f"{train_metrics.get('mape', 'N/A'):.4f}%"],
                ["R² (Coefficient of Determination)", f"{train_metrics.get('r2', 'N/A'):.4f}"]
            ]
            train_table = Table(train_data, colWidths=[2.5 * inch, 2.5 * inch])
            train_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#A23B72')),  # Purple header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8F9FA')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D1D1'))
            ]))
            story.append(train_table)
        else:
            story.append(Paragraph("No training set evaluation metrics", normal_style))
        story.append(Spacer(1, 20))

        # Test set evaluation metrics
        if test_metrics and test_samples > 0:
            story.append(Paragraph("Test Set Evaluation Metrics", heading_style))
            test_data = [
                ["Metric", "Value"],
                ["MAE (Mean Absolute Error)", f"{test_metrics.get('mae', 'N/A'):.4f}"],
                ["RMSE (Root Mean Square Error)", f"{test_metrics.get('rmse', 'N/A'):.4f}"],
                ["MAPE (Mean Absolute Percentage Error)", f"{test_metrics.get('mape', 'N/A'):.4f}%"],
                ["R² (Coefficient of Determination)", f"{test_metrics.get('r2', 'N/A'):.4f}"]
            ]
            test_table = Table(test_data, colWidths=[2.5 * inch, 2.5 * inch])
            test_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#18A999')),  # Cyan header
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8F9FA')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D1D1'))
            ]))
            story.append(test_table)
            story.append(Spacer(1, 20))

        # Performance summary
        story.append(Paragraph("Performance Summary", heading_style))

        # Evaluate based on R² value
        r2_train = train_metrics.get('r2', 0) if train_metrics else 0
        r2_test = test_metrics.get('r2', 0) if test_metrics else 0

        if r2_train >= 0.9:
            train_performance = "Excellent"
            train_color = colors.HexColor('#28A745')  # Green
        elif r2_train >= 0.7:
            train_performance = "Good"
            train_color = colors.HexColor('#17A2B8')  # Blue
        elif r2_train >= 0.5:
            train_performance = "Fair"
            train_color = colors.HexColor('#FFC107')  # Yellow
        else:
            train_performance = "Needs Improvement"
            train_color = colors.HexColor('#DC3545')  # Red

        if test_samples > 0:
            if r2_test >= 0.9:
                test_performance = "Excellent"
                test_color = colors.HexColor('#28A745')
            elif r2_test >= 0.7:
                test_performance = "Good"
                test_color = colors.HexColor('#17A2B8')
            elif r2_test >= 0.5:
                test_performance = "Fair"
                test_color = colors.HexColor('#FFC107')
            else:
                test_performance = "Needs Improvement"
                test_color = colors.HexColor('#DC3545')
        else:
            test_performance = "No Test Data"
            test_color = colors.HexColor('#6C757D')  # Gray

        performance_data = [
            ["Dataset", "R² Value", "Performance Rating"],
            ["Training Set", f"{r2_train:.4f}", train_performance],
            ["Test Set", f"{r2_test:.4f}" if test_samples > 0 else "N/A", test_performance]
        ]

        performance_table = Table(performance_data, colWidths=[2 * inch, 1.5 * inch, 2 * inch])
        performance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6C757D')),  # Gray header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (2, 1), (2, 1), train_color),
            ('TEXTCOLOR', (2, 2), (2, 2), test_color),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D1D1'))
        ]))
        story.append(performance_table)
        story.append(Spacer(1, 20))

        # Generation time
        story.append(Paragraph(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))

        # Build PDF
        doc.build(story)
        print(f"PDF report generated: {pdf_path}")
        return pdf_path

    except Exception as e:
        print(f"Failed to generate PDF report: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def load_data_from_database(origin, destination):
    """
    从数据库加载航线数据并映射字段名
    
    :param origin: 起始机场代码
    :param destination: 目标机场代码
    :return: DataFrame，列名为原CSV的列名
    """
    try:
        print("从数据库加载数据...")
        
        # 从数据库查询数据
        queryset = FlightMarketRecord.objects.filter(
            origin=origin,
            destination=destination
        ).values()
        
        if not queryset:
            print(f"! 数据库中未找到航线 {origin}-{destination} 的数据")
            return None
        
        # 转换为DataFrame
        df = pd.DataFrame(list(queryset))
        
        if df.empty:
            print(f"! 航线 {origin}-{destination} 数据为空")
            return None
        
        print(f"从数据库加载了 {len(df)} 条记录")
        
        # 从配置文件获取字段名映射
        field_to_csv_mapping = get_field_mapping()
        special_fields = get_special_fields()
        
        # 重命名列
        df = df.rename(columns=field_to_csv_mapping)
        
        # 处理特殊字段
        for field_name, field_config in special_fields.items():
            if field_config['type'] == 'boolean_to_int':
                csv_column = field_to_csv_mapping.get(field_name)
                if csv_column in df.columns:
                    df[csv_column] = df[csv_column].astype(int)
                    print(f"处理特殊字段: {field_name} -> {csv_column} (布尔转整数)")
        
        # 数据类型转换：确保数值字段为float类型，避免decimal.Decimal类型问题
        numeric_columns = []
        for col in df.columns:
            if col not in ['YearMonth', 'Origin', 'Destination', 'Equipment', 'International Flight', 'Region']:
                try:
                    # 尝试转换为数值类型
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    numeric_columns.append(col)
                except:
                    # 如果转换失败，保持原类型
                    pass
        
        print(f"数据类型转换完成，转换了 {len(numeric_columns)} 个数值列")
        print("数据字段名映射完成")
        return df
        
    except Exception as e:
        print(f"! 从数据库加载数据失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def pretrain_single_route(origin, destination, config):
    """
    训练单条航线的完整流程

    :param origin: 起始机场代码 (如 'CAN')
    :param destination: 目标机场代码 (如 'PEK')
    :param config: 配置字典
    :return: 训练状态 (成功/失败) 和结果信息
    """

    # print(f"\n=== 开始训练航线: {origin} -> {destination} ===")
    # print(f"配置: {config}")
    
    # 记录训练开始时间
    train_start_time = time.time()
    
    # 初始化日期变量，确保它们始终有默认值
    train_start_date = datetime.now().date()
    train_end_date = datetime.now().date()
    
    # 合并配置，用户配置优先级更高
    final_config = merge_model_params(
        granularity=config.get("time_granularity", "quarterly"),
        model_type=config.get("model_type", "lgb"),
        custom_params=config
    )
    
    print(f"最终配置: {final_config}")

    # 使用合并后的配置
    time_granularity = final_config["time_granularity"]
    model_type = final_config["model_type"]
    test_size = final_config["test_size"]
    add_ts_forecast = final_config["add_ts_forecast"]
    
    # 获取ARIMA参数，如果没有指定则使用默认值(1,1,1)
    arima_order = final_config.get("arima_order", (1, 1, 1))
    
    # 如果配置中分别指定了arima_p, arima_d, arima_q，则使用这些值
    if "arima_p" in config or "arima_d" in config or "arima_q" in config:
        arima_p = config.get("arima_p", 1)
        arima_d = config.get("arima_d", 1)
        arima_q = config.get("arima_q", 1)
        arima_order = (arima_p, arima_d, arima_q)

    current_dir = os.path.dirname(os.path.abspath(__file__))  # backend/predict/predictive_algorithm/
    PRE_TRAINED_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(current_dir)), 'AirlineModels', 'Pre_trained_Models')
    
    # 创建时间粒度和模型类型的子目录
    granularity_model_dir = os.path.join(PRE_TRAINED_MODEL_DIR, f"{time_granularity}_{model_type}")
    os.makedirs(granularity_model_dir, exist_ok=True)
    
    # 生成时间戳（精确到秒）
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    
    # 创建最终的航线目录
    route_dir = os.path.join(granularity_model_dir, f"{origin}_{destination}_{timestamp}")
    os.makedirs(route_dir, exist_ok=True)

    try:
        # 从数据库加载数据
        # print("从数据库加载数据...")
        domestic = load_data_from_database(origin, destination)
        
        if domestic is None:
            print(f"! 无法从数据库加载航线 {origin}-{destination} 的数据")
            return False, "无法从数据库加载数据"

        # 检查航线数据是否存在
        mask = (domestic['Origin'] == origin) & (domestic['Destination'] == destination)
        route_data = domestic[mask].copy()

        if route_data.empty:
            print(f"! 未找到航线 {origin}-{destination} 的数据")
            return False, "航线数据不存在"

        # print(f"找到 {len(route_data)} 条航线记录")

        # print(f"创建输出目录: {route_dir}")

        # 初始化组件
        preprocessor = DataPreprocessor(
            fill_method='interp',
            normalize=False,
            non_economic_tail_window=6,
        )

        granularity_controller = TimeGranularityController(time_granularity)

        ts_model = ARIMAModel(
            order=arima_order,
            freq=granularity_controller.get_freq()
        )

        feature_builder = FeatureBuilder(
            granularity_controller=granularity_controller,
            add_ts_forecast=add_ts_forecast,
            ts_model=ts_model
        )

        route_processor = AirlineRouteModel(
            data=domestic,
            preprocessor=preprocessor,
            feature_builder=feature_builder,
            granularity=time_granularity
        )

        # 准备数据
        # print("准备训练和测试数据...")
        X_train, y_train, X_test, y_test, data_with_features = route_processor.prepare_data(
            origin=origin,
            destination=destination,
            test_size=test_size
        )

        if X_train is None or X_train.empty:
            print(f"! 航线 {origin}-{destination} 数据不足，无法训练")
            return False, "数据不足"

        # print(f"训练集样本数: {len(X_train)}")
        # print(f"测试集样本数: {len(X_test) if X_test is not None else 0}")
        # print(f"特征数量: {len(X_train.columns)}")
        
        # 获取训练数据的日期范围
        train_start_date = data_with_features[route_processor.date_col].min()
        train_end_date = data_with_features[route_processor.date_col].max()
        # print(f"训练数据日期范围: {train_start_date.strftime('%Y-%m-%d')} 到 {train_end_date.strftime('%Y-%m-%d')}")

        # 训练模型
        print(f"训练 {model_type.upper()} 模型...")
        
        # 根据模型类型选择相应的参数
        if model_type == "lgb":
            model_params = final_config.get("lgb_params", {})
        else:  # xgb
            model_params = final_config.get("xgb_params", {})
            
        model = get_model(time_granularity, model_type, model_params)
        model.fit(X_train, y_train)

        # 评估模型性能...")
        train_preds = model.predict(X_train)
        train_evaluator = ModelEvaluator(y_train, train_preds)

        test_preds = None
        test_evaluator = None
        if time_granularity != 'yearly' and X_test is not None and not X_test.empty:
            test_preds = model.predict(X_test)
            test_evaluator = ModelEvaluator(y_test, test_preds)

        # 保存data_with_features数据
        print("保存特征工程后的数据...")
        data_with_features_path = os.path.join(route_dir, "data_with_features.csv")
        data_with_features.to_csv(data_with_features_path, index=False)
        print(f"特征数据已保存到: {data_with_features_path}")

        # 保存评估结果
        
        # print("保存评估结果...")
        with open(os.path.join(route_dir, "evaluation.txt"), "w", encoding='utf-8') as f:
            f.write("==== 训练集评估 ====\n")
            f.write(train_evaluator.report("Train", return_str=True))

            if test_preds is not None:
                f.write("\n\n==== 测试集评估 ====\n")
                f.write(test_evaluator.report("Test", return_str=True))

        # # 特征重要性
        # print("生成特征重要性图...")
        # if model_type == "lgb":
        #     lgb.plot_importance(model, max_num_features=20)
        # else:
        #     xgb.plot_importance(model, max_num_features=20)
        # plt.savefig(os.path.join(route_dir, "feature_importance.png"))
        # plt.close()

        # 保存元数据
        metadata = {
            "feature_columns": X_train.columns.tolist(),
            "date_column": route_processor.date_col,
            "target_column": route_processor.target_col,
            "time_granularity": time_granularity,
            "model_type": model_type,
            "arima_order": arima_order,
            "model_params": model_params,
            # "last_complete_date": data_with_features_full[route_processor.date_col].max().strftime('%Y-%m-%d'),
            "feature_count": len(X_train.columns),
            "training_samples": len(X_train),
            "test_samples": len(X_test) if X_test is not None else 0,
            "train_mae": train_evaluator.calculate_metrics().get('mae'),
            "train_rmse": train_evaluator.calculate_metrics().get('rmse'),
            "train_mape": train_evaluator.calculate_metrics().get('mape'),
            "train_r2": train_evaluator.calculate_metrics().get('r2'),
            "test_mae": test_evaluator.calculate_metrics().get('mae') if test_evaluator else None,
            "test_rmse": test_evaluator.calculate_metrics().get('rmse') if test_evaluator else None,
            "test_mape": test_evaluator.calculate_metrics().get('mape') if test_evaluator else None,
            "test_r2": test_evaluator.calculate_metrics().get('r2') if test_evaluator else None,
            # 保存完整的配置信息
            "complete_config": final_config
        }
        with open(os.path.join(route_dir, "metadata.json"), "w", encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        # 计算训练耗时
        train_end_time = time.time()
        train_duration_seconds = train_end_time - train_start_time
        train_duration = timedelta(seconds=train_duration_seconds)
        
        # 生成PDF报告
        print("生成PDF报告...")
        report_pdf_path = generate_model_report(
            route_dir=route_dir,
            origin=origin,
            destination=destination,
            time_granularity=time_granularity,
            model_type=model_type,
            train_metrics=train_evaluator.calculate_metrics(),
            test_metrics=test_evaluator.calculate_metrics() if test_evaluator else None,
            training_samples=len(X_train),
            test_samples=len(X_test) if X_test is not None else 0,
            feature_count=len(X_train.columns),
            train_start_date=train_start_date,
            train_end_date=train_end_date,
            train_duration=train_duration
        )

        # 返回成功状态和结果信息，支持创建PretrainRecord实例
        # 计算相对于PRE_TRAINED_MODEL_DIR的相对路径
        meta_file_relative_path = os.path.relpath(os.path.join(route_dir, "metadata.json"), PRE_TRAINED_MODEL_DIR)
        report_pdf_relative_path = os.path.relpath(report_pdf_path, PRE_TRAINED_MODEL_DIR) if report_pdf_path else None
        data_with_features_relative_path = os.path.relpath(data_with_features_path, PRE_TRAINED_MODEL_DIR)
        
        result_info = {
            "origin": origin,
            "destination": destination,
            "meta_file_path": meta_file_relative_path,
            "train_start_date": train_start_date,
            "train_end_date": train_end_date,
            "time_granularity": time_granularity,
            "step_size": test_size,
            "train_datetime": datetime.now(),
            "train_duration": train_duration,
            "train_mae": train_evaluator.calculate_metrics().get('mae'),
            "train_rmse": train_evaluator.calculate_metrics().get('rmse'),
            "train_mape": train_evaluator.calculate_metrics().get('mape'),
            "train_r2": train_evaluator.calculate_metrics().get('r2'),
            "test_mae": test_evaluator.calculate_metrics().get('mae') if test_evaluator else None,
            "test_rmse": test_evaluator.calculate_metrics().get('rmse') if test_evaluator else None,
            "test_mape": test_evaluator.calculate_metrics().get('mape') if test_evaluator else None,
            "test_r2": test_evaluator.calculate_metrics().get('r2') if test_evaluator else None,
            "report_pdf": report_pdf_relative_path,
            "data_with_features_path": data_with_features_relative_path,
            "success": True,
            "use_pretrain": False
        }

        return True, result_info

    except Exception as e:
        print(f"! 航线 {origin}-{destination} 训练失败: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # 确保在异常情况下也有有效的日期值
        try:
            if 'train_start_date' not in locals() or pd.isna(train_start_date):
                train_start_date = datetime.now().date()
            if 'train_end_date' not in locals() or pd.isna(train_end_date):
                train_end_date = datetime.now().date()
        except:
            train_start_date = datetime.now().date()
            train_end_date = datetime.now().date()
        
        result_info = {
            "origin": origin,
            "destination": destination,
            "meta_file_path": "-",
            "train_start_date": train_start_date,
            "train_end_date": train_end_date,
            "time_granularity": time_granularity,
            "step_size": test_size,
            "train_datetime": datetime.now(),
            "train_duration": 0,
            "success": False,
            "error": str(e),
        }
        return False, result_info


# 使用示例
if __name__ == "__main__":
    
    # 示例：完整自定义配置
    custom_config = {
        # 基础配置
        "time_granularity": "quarterly",
        "model_type": "xgb",
        "test_size": 8,
        "add_ts_forecast": True,
        
        # ARIMA参数
        "arima_order": (2, 1, 2),
        
        # XGBoost参数
        "xgb_params": {
            "n_estimators": 200,
            "max_depth": 5,
            "learning_rate": 0.05,
            "reg_lambda": 2,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_alpha": 0.2,
            "min_child_weight": 3
        }
    }
    
    # 示例：LightGBM优化配置
    lgb_config = {
        "time_granularity": "monthly",
        "model_type": "lgb",
        "test_size": 12,
        "add_ts_forecast": False,  # 不使用时序预测
        
        # LightGBM参数
        "lgb_params": {
            "n_estimators": 300,
            "max_depth": 10,
            "min_child_samples": 5,
            "learning_rate": 0.03,
            "subsample": 0.7,
            "colsample_bytree": 0.7,
            "reg_alpha": 0.05,
            "reg_lambda": 0.05,
            "num_leaves": 31,
            "feature_fraction": 0.8
        }
    }
    
    print("\n=== 测试完整自定义配置 ===")
    success2, result2 = pretrain_single_route("CAN", "PVG", custom_config)
    
    print("\n=== 测试LightGBM优化配置 ===")
    success3, result3 = pretrain_single_route("CAN", "SHA", lgb_config)
