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
    baseURL: 'https://your-production-server.com', // 生产环境服务器地址
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
    STATISTICS_SUMMARY: '/show/statistics/summary/',
    STATISTICS_TREND: '/show/statistics/trend/',
  },
  // 预测相关API
  PREDICT: {
    FORECAST: '/predict/forecast/',
    MODEL_STATUS: '/predict/model-status/',
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