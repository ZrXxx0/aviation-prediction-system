import xgboost as xgb
import lightgbm as lgb


def get_model(granularity, model_type='lgb', model_params=None):
    """根据时间粒度和模型类型返回配置好的模型
    
    Args:
        granularity (str): 时间粒度 ('monthly', 'quarterly', 'yearly')
        model_type (str): 模型类型 ('lgb', 'xgb')
        model_params (dict): 模型参数字典，如果为None则使用默认参数
    """
    if model_type == 'lgb':
        # 硬编码的LightGBM默认参数
        default_params = {
            'monthly': {
                'n_estimators': 100,
                'max_depth': 7,
                'min_child_samples': 10,
                'min_split_gain': 0.0,
                'learning_rate': 0.1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'num_leaves': 31,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'min_data_in_leaf': 20,
                'verbose': -1
            },
            'quarterly': {
                'n_estimators': 100,
                'max_depth': 2,
                'min_child_samples': 2,
                'min_split_gain': 0.0,
                'learning_rate': 0.1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'num_leaves': 31,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'min_data_in_leaf': 20,
                'verbose': -1
            },
            'yearly': {
                'n_estimators': 100,
                'max_depth': 3,
                'min_child_samples': 1,
                'min_split_gain': 0.0,
                'learning_rate': 0.1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'num_leaves': 31,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'min_data_in_leaf': 20,
                'verbose': -1
            }
        }
        
        # 获取默认参数
        base_params = default_params.get(granularity, default_params['quarterly'])
        
        # 如果用户提供了参数，则覆盖默认参数
        if model_params:
            base_params.update(model_params)
        
        # 在Windows环境下禁用并行处理以避免joblib问题
        base_params['n_jobs'] = 1
        return lgb.LGBMRegressor(**base_params)
        
    else:  # xgb
        # 硬编码的XGBoost默认参数
        default_params = {
            'monthly': {
                'n_estimators': 100,
                'max_depth': 3,
                'learning_rate': 0.1,
                'reg_lambda': 1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'min_child_weight': 1,
                'gamma': 0,
                'max_delta_step': 0,
                'scale_pos_weight': 1,
                'colsample_bylevel': 1,
                'colsample_bynode': 1,
                'tree_method': 'auto'
            },
            'quarterly': {
                'n_estimators': 100,
                'max_depth': 2,
                'learning_rate': 0.1,
                'reg_lambda': 1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'min_child_weight': 1,
                'gamma': 0,
                'max_delta_step': 0,
                'scale_pos_weight': 1,
                'colsample_bylevel': 1,
                'colsample_bynode': 1,
                'tree_method': 'auto'
            },
            'yearly': {
                'n_estimators': 100,
                'max_depth': 2,
                'learning_rate': 0.1,
                'reg_lambda': 1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'min_child_weight': 1,
                'gamma': 0,
                'max_delta_step': 0,
                'scale_pos_weight': 1,
                'colsample_bylevel': 1,
                'colsample_bynode': 1,
                'tree_method': 'auto'
            }
        }
        
        # 获取默认参数
        base_params = default_params.get(granularity, default_params['quarterly'])
        
        # 如果用户提供了参数，则覆盖默认参数
        if model_params:
            base_params.update(model_params)
        
        return xgb.XGBRegressor(**base_params)


def get_default_config(granularity='quarterly', model_type='lgb'):
    """获取指定时间粒度和模型类型的默认配置
    
    Args:
        granularity (str): 时间粒度 ('monthly', 'quarterly', 'yearly')
        model_type (str): 模型类型 ('lgb', 'xgb')
        
    Returns:
        dict: 默认配置字典
    """
    # 基础默认配置
    default_config = {
        'time_granularity': granularity,
        'model_type': model_type,
        'test_size': 8,
        'add_ts_forecast': True,
        'arima_order': (1, 1, 1),
    }
    
    # 根据时间粒度调整默认值
    if granularity == 'monthly':
        default_config.update({
            'test_size': 12,
            'arima_order': (1, 1, 1)
        })
    elif granularity == 'yearly':
        default_config.update({
            'test_size': 5,
            'add_ts_forecast': False,
            'arima_order': (1, 1, 1)
        })
    
    # 添加模型特定参数
    if model_type == 'lgb':
        if granularity == 'monthly':
            default_config['lgb_params'] = {
                'n_estimators': 100,
                'max_depth': 7,
                'min_child_samples': 10,
                'min_split_gain': 0.0,
                'learning_rate': 0.1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'num_leaves': 31,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'min_data_in_leaf': 20,
                'verbose': -1
            }
        elif granularity == 'quarterly':
            default_config['lgb_params'] = {
                'n_estimators': 100,
                'max_depth': 2,
                'min_child_samples': 2,
                'min_split_gain': 0.0,
                'learning_rate': 0.1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'num_leaves': 31,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'min_data_in_leaf': 20,
                'verbose': -1
            }
        else:  # yearly
            default_config['lgb_params'] = {
                'n_estimators': 100,
                'max_depth': 3,
                'min_child_samples': 1,
                'min_split_gain': 0.0,
                'learning_rate': 0.1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'reg_lambda': 0.1,
                'num_leaves': 31,
                'feature_fraction': 0.8,
                'bagging_fraction': 0.8,
                'bagging_freq': 5,
                'min_data_in_leaf': 20,
                'verbose': -1
            }
    else:  # xgb
        if granularity == 'monthly':
            default_config['xgb_params'] = {
                'n_estimators': 100,
                'max_depth': 3,
                'learning_rate': 0.1,
                'reg_lambda': 1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'min_child_weight': 1,
                'gamma': 0,
                'max_delta_step': 0,
                'scale_pos_weight': 1,
                'colsample_bylevel': 1,
                'colsample_bynode': 1,
                'tree_method': 'auto'
            }
        elif granularity == 'quarterly':
            default_config['xgb_params'] = {
                'n_estimators': 100,
                'max_depth': 2,
                'learning_rate': 0.1,
                'reg_lambda': 1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'min_child_weight': 1,
                'gamma': 0,
                'max_delta_step': 0,
                'scale_pos_weight': 1,
                'colsample_bylevel': 1,
                'colsample_bynode': 1,
                'tree_method': 'auto'
            }
        else:  # yearly
            default_config['xgb_params'] = {
                'n_estimators': 100,
                'max_depth': 2,
                'learning_rate': 0.1,
                'reg_lambda': 1,
                'random_state': 42,
                'subsample': 0.8,
                'colsample_bytree': 0.8,
                'reg_alpha': 0.1,
                'min_child_weight': 1,
                'gamma': 0,
                'max_delta_step': 0,
                'scale_pos_weight': 1,
                'colsample_bylevel': 1,
                'colsample_bynode': 1,
                'tree_method': 'auto'
            }
    
    return default_config


def merge_model_params(granularity, model_type, custom_params=None):
    """合并模型参数，返回最终的参数字典
    
    Args:
        granularity (str): 时间粒度
        model_type (str): 模型类型
        custom_params (dict): 用户自定义参数
        
    Returns:
        dict: 合并后的参数字典
    """
    # 获取默认配置
    default_config = get_default_config(granularity, model_type)
    
    if custom_params is None:
        return default_config
    
    # 智能合并配置：只覆盖用户明确指定的参数
    import copy
    merged = copy.deepcopy(default_config)
    
    def smart_merge(default_dict, custom_dict):
        """智能合并字典：只覆盖用户明确指定的参数"""
        for key, value in custom_dict.items():
            if key in default_dict:
                if isinstance(default_dict[key], dict) and isinstance(value, dict):
                    # 递归合并嵌套字典
                    smart_merge(default_dict[key], value)
                else:
                    # 直接覆盖非字典值
                    default_dict[key] = value
            else:
                # 如果默认配置中没有这个键，直接添加
                default_dict[key] = value
    
    smart_merge(merged, custom_params)
    return merged