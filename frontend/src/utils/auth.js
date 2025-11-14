// 用户认证相关工具函数

/**
 * 获取token
 */
export function getToken() {
  return localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token')
}

/**
 * 设置token
 */
export function setToken(token, remember = true) {
  if (remember) {
    localStorage.setItem('auth_token', token)
  } else {
    sessionStorage.setItem('auth_token', token)
  }
}

/**
 * 移除token
 */
export function removeToken() {
  localStorage.removeItem('auth_token')
  sessionStorage.removeItem('auth_token')
}

/**
 * 获取用户信息
 */
export function getUserInfo() {
  const userStr = localStorage.getItem('user_info') || sessionStorage.getItem('user_info')
  if (userStr) {
    try {
      return JSON.parse(userStr)
    } catch (e) {
      return null
    }
  }
  return null
}

/**
 * 设置用户信息
 */
export function setUserInfo(userInfo, remember = true) {
  const userStr = JSON.stringify(userInfo)
  if (remember) {
    localStorage.setItem('user_info', userStr)
  } else {
    sessionStorage.setItem('user_info', userStr)
  }
}

/**
 * 移除用户信息
 */
export function removeUserInfo() {
  localStorage.removeItem('user_info')
  sessionStorage.removeItem('user_info')
}

/**
 * 检查用户是否有特定权限
 */
export function hasPermission(permission) {
  const userInfo = getUserInfo()
  if (!userInfo || !userInfo.permissions) {
    return false
  }
  return userInfo.permissions.includes(permission)
}

/**
 * 检查用户角色
 */
export function hasRole(roleName) {
  const userInfo = getUserInfo()
  if (!userInfo) {
    return false
  }
  return userInfo.role_name === roleName
}

/**
 * 是否可以查看系统管理
 */
export function canViewAdministration() {
  return hasRole('super_admin')
}

/**
 * 是否可以查看预测模块
 */
export function canViewForecast() {
  return hasRole('super_admin') || hasRole('admin')
}

/**
 * 是否可以查看数据管理
 */
export function canViewManagement() {
  return hasRole('super_admin') || hasRole('admin')
}

/**
 * 清除所有认证信息
 */
export function clearAuth() {
  removeToken()
  removeUserInfo()
}

