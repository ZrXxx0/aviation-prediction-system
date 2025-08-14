import os
import pickle
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")


def setup_numpy_compatibility():
    """
    设置numpy兼容性环境，解决pickle加载时的版本兼容性问题
    """
    import sys
    import types
    
    # 处理numpy._core模块缺失的问题
    if 'numpy._core' not in sys.modules:
        try:
            import numpy._core
        except ImportError:
            # 创建兼容性模块
            numpy_core_module = types.ModuleType('numpy._core')
            sys.modules['numpy._core'] = numpy_core_module
            
            # 添加常用的属性和方法
            numpy_core_module._dtype = type(np.dtype('float64'))
            numpy_core_module._dtype_kind = lambda x: 'f' if 'float' in str(x) else 'i' if 'int' in str(x) else 'u'
            numpy_core_module._dtype_ = lambda x: x
            numpy_core_module._dtype_subclass = lambda x: x
    
    # 处理其他可能的numpy版本兼容性问题
    if 'numpy.core' not in sys.modules:
        try:
            import numpy.core
        except ImportError:
            pass

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class PredictionFromSavedModels:
    def __init__(self, base_results_dir):
        self.base_results_dir = base_results_dir
        self.available_routes = self._get_available_routes()
        
    def _get_available_routes(self):
        routes = []
        for item in os.listdir(self.base_results_dir):
            item_path = os.path.join(self.base_results_dir, item)
            if os.path.isdir(item_path) and '_' in item:
                required_files = ['model.pkl', 'preprocessor.pkl', 'feature_builder.pkl', 
                                'metadata.json', 'latest_data.csv']
                if all(os.path.exists(os.path.join(item_path, f)) for f in required_files):
                    routes.append(item)
        return routes
    
    def load_model_for_route(self, route_name):
        route_dir = os.path.join(self.base_results_dir, route_name)
        
        if not os.path.exists(route_dir):
            raise FileNotFoundError(f"航线目录不存在: {route_dir}")
        
        try:
            # 设置numpy兼容性环境
            setup_numpy_compatibility()
            
            with open(os.path.join(route_dir, "model.pkl"), "rb") as f:
                model = pickle.load(f)
            
            with open(os.path.join(route_dir, "preprocessor.pkl"), "rb") as f:
                preprocessor = pickle.load(f)
            
            with open(os.path.join(route_dir, "feature_builder.pkl"), "rb") as f:
                feature_builder = pickle.load(f)
            
            with open(os.path.join(route_dir, "metadata.json"), "r", encoding='utf-8') as f:
                metadata = json.load(f)
            
            latest_data = pd.read_csv(os.path.join(route_dir, "latest_data.csv"))
            latest_data['YearMonth'] = pd.to_datetime(latest_data['YearMonth'])
            
            return {
                'model': model,
                'preprocessor': preprocessor,
                'feature_builder': feature_builder,
                'metadata': metadata,
                'latest_data': latest_data,
                'route_dir': route_dir
            }
            
        except Exception as e:
            raise Exception(f"加载航线 {route_name} 的模型失败: {str(e)}")
    
    def predict_future(self, route_name, future_periods=36, save_results=True, plot_results=True):
        print(f"\n=== 开始预测航线: {route_name} ===")
        
        components = self.load_model_for_route(route_name)
        model = components['model']
        preprocessor = components['preprocessor']
        feature_builder = components['feature_builder']
        metadata = components['metadata']
        latest_data = components['latest_data']
        route_dir = components['route_dir']
        
        feature_cols = metadata['feature_columns']
        date_col = metadata['date_column']
        time_granularity = metadata['time_granularity']
        last_complete_date = pd.to_datetime(metadata['last_complete_date'])
        
        if time_granularity == 'quarterly':
            future_periods = future_periods // 3
        elif time_granularity == 'yearly':
            future_periods = future_periods // 12
        
        print(f"时间粒度: {time_granularity}")
        print(f"预测期数: {future_periods}")
        print(f"最后完整日期: {last_complete_date.strftime('%Y-%m-%d')}")
        
        if time_granularity == 'quarterly':
            while last_complete_date.month not in [3, 6, 9, 12]:
                last_complete_date -= pd.DateOffset(months=1)
        elif time_granularity == 'yearly':
            while last_complete_date.month != 12:
                last_complete_date -= pd.DateOffset(months=1)
        
        future_preds = []
        current_data = latest_data.copy()
        
        for i in range(future_periods):
            if time_granularity == 'monthly':
                offset = pd.DateOffset(months=1)
            elif time_granularity == 'quarterly':
                offset = pd.DateOffset(months=3)
            else:
                offset = pd.DateOffset(years=1)
            
            next_date = last_complete_date + offset
            
            next_row = {date_col: next_date}
            for col in current_data.columns:
                if col != date_col:
                    next_row[col] = np.nan
            
            current_data = pd.concat([current_data, pd.DataFrame([next_row])], ignore_index=True)
            current_data = preprocessor.fit_transform(current_data)
            current_data = feature_builder.fit_transform(current_data)
            
            latest_input = current_data.iloc[[-1]][feature_cols]
            next_pred = model.predict(latest_input)[0]
            
            current_data.loc[current_data.index[-1], metadata['target_column']] = next_pred
            
            future_preds.append({
                'YearMonth': next_date,
                'Predicted': next_pred
            })
            
            last_complete_date = next_date
            print(f"  预测 {next_date.strftime('%Y-%m-%d')}: {next_pred:.0f}")
        
        future_df = pd.DataFrame(future_preds)
        future_df['Actual'] = np.nan
        future_df['Set'] = 'Future'
        
        if save_results:
            output_file = os.path.join(route_dir, f"future_prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            future_df.to_csv(output_file, index=False)
            print(f"√ 预测结果已保存到: {output_file}")
        
        if plot_results:
            self._plot_predictions(route_name, latest_data, future_df, metadata, route_dir)
        
        return future_df
    
    def _plot_predictions(self, route_name, historical_data, future_df, metadata, route_dir):
        try:
            plt.figure(figsize=(14, 8))
            
            date_col = metadata['date_column']
            target_col = metadata['target_column']
            
            plt.plot(historical_data[date_col], historical_data[target_col], 
                    label='历史数据', color='blue', linewidth=2)
            
            plt.plot(future_df['YearMonth'], future_df['Predicted'], 
                    label='未来预测', color='red', linewidth=2, linestyle='--')
            
            last_historical_date = historical_data[date_col].max()
            plt.axvline(x=last_historical_date, color='gray', linestyle=':', 
                       label='历史/预测分割线', linewidth=2)
            
            plt.title(f"航线座位预测: {route_name.replace('_', ' → ')}", fontsize=16)
            plt.xlabel("日期", fontsize=12)
            plt.ylabel("座位数", fontsize=12)
            plt.legend(fontsize=12)
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            plot_file = os.path.join(route_dir, f"future_prediction_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(plot_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"√ 预测图表已保存到: {plot_file}")
            
        except Exception as e:
            print(f"! 生成图表失败: {str(e)}")
    
    def batch_predict_all_routes(self, future_periods=36, save_results=True, plot_results=True):
        print(f"=== 开始批量预测 {len(self.available_routes)} 条航线 ===")
        print(f"可用航线: {', '.join(self.available_routes)}")
        
        results_summary = []
        
        for route in self.available_routes:
            try:
                future_df = self.predict_future(
                    route, 
                    future_periods=future_periods,
                    save_results=save_results,
                    plot_results=plot_results
                )
                
                results_summary.append({
                    'route': route,
                    'status': 'success',
                    'prediction_periods': len(future_df),
                    'last_prediction_date': future_df['YearMonth'].max().strftime('%Y-%m-%d'),
                    'avg_prediction': future_df['Predicted'].mean()
                })
                
            except Exception as e:
                print(f"! 航线 {route} 预测失败: {str(e)}")
                results_summary.append({
                    'route': route,
                    'status': 'failed',
                    'error': str(e)
                })
        
        if save_results:
            summary_df = pd.DataFrame(results_summary)
            summary_file = os.path.join(self.base_results_dir, 
                                      f"prediction_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
            print(f"\n√ 预测摘要已保存到: {summary_file}")
        
        success_count = len([r for r in results_summary if r['status'] == 'success'])
        failed_count = len([r for r in results_summary if r['status'] == 'failed'])
        
        print(f"\n=== 批量预测完成 ===")
        print(f"成功: {success_count}, 失败: {failed_count}")
        
        return results_summary
    
    def get_route_info(self, route_name):
        try:
            components = self.load_model_for_route(route_name)
            metadata = components['metadata']
            
            print(f"\n=== 航线 {route_name} 信息 ===")
            print(f"时间粒度: {metadata['time_granularity']}")
            print(f"模型类型: {metadata['model_type']}")
            print(f"特征数量: {metadata['feature_count']}")
            print(f"训练样本数: {metadata['training_samples']}")
            print(f"测试样本数: {metadata['test_samples']}")
            print(f"最后完整日期: {metadata['last_complete_date']}")
            print(f"特征列: {', '.join(metadata['feature_columns'][:5])}...")
            
            return metadata
            
        except Exception as e:
            print(f"! 获取航线信息失败: {str(e)}")
            return None

def main():
    BASE_RESULTS_DIR = './results_split0813/quarterly_lgb'
    
    if not os.path.exists(BASE_RESULTS_DIR):
        print(f"! 结果目录不存在: {BASE_RESULTS_DIR}")
        return
    
    predictor = PredictionFromSavedModels(BASE_RESULTS_DIR)
    
    print(f"找到 {len(predictor.available_routes)} 条可用航线")
    
    if predictor.available_routes:
        sample_route = predictor.available_routes[0]
        print(f"\n示例: 预测航线 {sample_route}")
        
        predictor.get_route_info(sample_route)
        
        future_df = predictor.predict_future(sample_route, future_periods=36)
        print(f"预测完成，共 {len(future_df)} 期")
    
    print(f"\n是否进行批量预测所有航线? (y/n): ", end="")
    user_input = input().strip().lower()
    
    if user_input == 'y':
        predictor.batch_predict_all_routes(future_periods=36)

if __name__ == "__main__":
    main()
