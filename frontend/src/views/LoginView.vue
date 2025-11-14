<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <div class="login-title">系统登录</div>

      <el-form :model="form" :rules="rules" ref="formRef" label-position="top" class="login-form">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" autocomplete="username" />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password autocomplete="current-password" />
        </el-form-item>

        <el-form-item>
          <el-checkbox v-model="form.remember">记住我</el-checkbox>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onSubmit" style="width:100%;">登录</el-button>
        </el-form-item>

        <div class="login-links">
          <el-link type="primary" @click="goTo('/dashboard')">游客试用</el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import apiConfig from '@/config/api.js'

const router = useRouter()
const loading = ref(false)
const formRef = ref(null)

const form = reactive({
  email: '',
  password: '',
  remember: true
})

const rules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效邮箱', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码最少6位', trigger: 'blur' }
  ]
}

async function onSubmit() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    const endpoint = apiConfig.endpoints?.AUTH?.LOGIN || '/auth/login/'
    const url = apiConfig.getUrl ? apiConfig.getUrl(endpoint) : endpoint

    const payload = { email: form.email.trim(), password: form.password }
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`)
    }
    const data = await res.json()

    if (data && data.success && data.data?.token) {
      const token = data.data.token
      const userInfo = data.data.user
      
      // 保存token和用户信息
      const { setToken, setUserInfo } = await import('@/utils/auth')
      setToken(token, form.remember)
      if (userInfo) {
        setUserInfo(userInfo, form.remember)
      }
      
      ElMessage.success('登录成功')
      router.replace({ path: '/dashboard' })
    } else {
      const msg = data?.message || '登录失败，请检查账号或密码'
      ElMessage.error(msg)
    }
  } catch (e) {
    console.error('登录请求失败:', e)
    ElMessage.error('登录失败：' + (e.message || '网络错误'))
  } finally {
    loading.value = false
  }
}

function goTo(path) {
  router.push(path)
}
</script>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: calc(100vh - 0px);
  background: linear-gradient(135deg, #f5f7fa 0%, #c3dafe 100%);
  padding: 20px;
}
.login-card {
  width: 380px;
  padding: 24px;
}
.login-title {
  font-size: 20px;
  font-weight: 600;
  text-align: center;
  margin-bottom: 16px;
}
.login-form .el-form-item {
  margin-bottom: 12px;
}
.login-links {
  text-align: center;
  margin-top: 8px;
}
</style>