// API配置文件
// 支持不同环境的API配置

// 环境配置
const ENV = process.env.NODE_ENV || 'development';

// API基础配置
const API_CONFIG = {
  development: {
    baseURL: 'http://localhost:8000',
    timeout: 10000,
  },
  production: {
    baseURL: 'http://localhost:8000', // 生产环境服务器地址
    timeout: 15000,
  },
  staging: {
    baseURL: 'https://your-staging-server.com', // 测试环境服务器地址
    timeout: 12000,
  }
};

// 获取当前环境的配置
const getCurrentConfig = () => {
  return API_CONFIG[ENV] || API_CONFIG.development;
};

// API端点配置
const API_ENDPOINTS = {
  // 数据展示相关API
  SHOW: {
    ROUTES: '/show/routes/',
    ROUTE_DISTRIBUTION: '/show/routes/',
    ROUTE_DISTRIBUTION_ADVANCED: '/show/routes/advanced/',
    STATISTICS_SUMMARY: '/show/statistics/summary/',
    STATISTICS_TREND: '/show/statistics/trend/',
    AIRCRAFT_DATA: '/show/statistics/aircraft-data/',
  },
  // 预测相关API
  PREDICT: {
    UPDATE: '/predict/forecast/update_topn/',
    LOGS: '/predict/forecast/update_topn_logs/',
    SHOW: '/predict/forecast/show/',
    MODELS: '/predict/forecast/models/',
    FORECAST: '/predict/forecast/run/',
    PRETRAIN: '/predict/pretrain/model/',
    MODEL_STATUS: '/predict/model-status/',
    TRAIN: '/predict/formal/train/',
    FLIGHTDATA: '/predict/data/get_flightdata/',
    DOWNLOAD_TRAIN_FILE: '/predict/train_file/save_locate/',
    UPLOAD_CHECK: '/predict/data/upload/check/',
    UPLOAD_INSERT: '/predict/data/upload/insert/',
    UPLOAD_RESOLVE: '/predict/data/upload/resolve/',
  },
  // 认证相关API
  AUTH: {
    LOGIN: '/auth/login/',
    LOGOUT: '/auth/logout/',
    USER_INFO: '/auth/user/info/',
    ROLES: '/auth/roles/',
  },
  // 用户管理API（需要超级管理员权限）
  ADMIN: {
    LIST_USERS: '/auth/users/',
    CREATE_USER: '/auth/users/',
    UPDATE_USER: '/auth/users/{id}/',
    DELETE_USER: '/auth/users/{id}/',
  },
  // 其他API端点可以在这里添加
};

// 构建完整的API URL
const buildApiUrl = (endpoint) => {
  const config = getCurrentConfig();
  return `${config.baseURL}${endpoint}`;
};

// 导出配置
export default {
  // 获取基础URL
  getBaseURL: () => getCurrentConfig().baseURL,
  
  // 获取超时时间
  getTimeout: () => getCurrentConfig().timeout,
  
  // 获取完整API URL
  getUrl: (endpoint) => buildApiUrl(endpoint),
  
  // API端点
  endpoints: API_ENDPOINTS,
  
  // 当前环境
  getEnvironment: () => ENV,
  
  // 是否为开发环境
  isDevelopment: () => ENV === 'development',
  
  // 是否为生产环境
  isProduction: () => ENV === 'production',
};

// 导出默认配置对象
export const apiConfig = {
  baseURL: getCurrentConfig().baseURL,
  timeout: getCurrentConfig().timeout,
  endpoints: API_ENDPOINTS,
}; 