<template>
  <div class="admin-container">
    <div class="admin-header">
      <h2>系统管理 - 用户与权限</h2>
      <div class="actions">
        <el-button type="primary" icon="el-icon-plus" @click="openAddDialog">新增用户</el-button>
        <el-button type="default" @click="loadUsers">刷新</el-button>
      </div>
    </div>

    <el-card class="admin-card">
      <el-table :data="users" stripe style="width:100%">
        <el-table-column prop="username" label="用户名" width="180" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column label="角色" width="180">
          <template #default="scope">
            <el-tag type="info">
              {{ scope.row.role_display || '未分配' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button type="text" size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button type="text" size="small" style="color:#f56c6c" @click="confirmDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="users.length === 0" class="empty-tip">暂无用户，请点击“新增用户”添加。</div>
    </el-card>

    <!-- 新增/编辑 用户弹窗 -->
    <el-dialog :title="isEditing ? '编辑用户' : '新增用户'" v-model="showDialog" width="520px" :close-on-click-modal="false">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="off" />
        </el-form-item>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" autocomplete="off" />
        </el-form-item>

        <el-form-item v-if="!isEditing" label="密码" prop="password">
          <el-input v-model="form.password" type="password" autocomplete="new-password" />
        </el-form-item>

        <el-form-item label="角色" prop="role_id">
          <el-select v-model="form.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option
              v-for="role in availableRoles"
              :key="role.id"
              :label="role.display_name"
              :value="role.id"
            >
              <span>{{ role.display_name }}</span>
              <span style="color: #8492a6; font-size: 13px; margin-left: 8px;">{{ role.description }}</span>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="可选：手机号码" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">{{ isEditing ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- 删除确认 -->
    <el-dialog title="确认删除" v-model="showDeleteConfirm" width="420px" :close-on-click-modal="false">
      <div>确认删除用户 <strong>{{ targetUser?.username }}</strong> ? 此操作不可恢复。</div>
      <template #footer>
        <el-button @click="showDeleteConfirm = false">取消</el-button>
        <el-button type="danger" :loading="deleting" @click="deleteUser">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import apiConfig from '@/config/api.js'

const users = ref([])
const availableRoles = ref([])
const showDialog = ref(false)
const showDeleteConfirm = ref(false)
const isEditing = ref(false)
const saving = ref(false)
const deleting = ref(false)
const targetUser = ref(null)
const formRef = ref(null)

const form = reactive({
  id: null,
  username: '',
  email: '',
  password: '',
  role_id: null,
  phone: ''
})

// 基础验证规则
const baseRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' }
  ]
}

// 根据编辑模式动态返回验证规则
const rules = computed(() => {
  if (isEditing.value) {
    // 编辑模式下，密码不是必填的
    const editRules = { ...baseRules }
    delete editRules.password
    return editRules
  }
  return baseRules
})

// 加载角色列表
async function loadRoles() {
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.AUTH.ROLES)
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token')
    const res = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data && data.success && Array.isArray(data.data)) {
      availableRoles.value = data.data
    }
  } catch (e) {
    console.error('加载角色失败:', e)
    ElMessage.error('加载角色列表失败')
  }
}

// 加载用户列表
async function loadUsers() {
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.ADMIN.LIST_USERS)
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token')
    const res = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    if (!res.ok) {
      if (res.status === 403) {
        ElMessage.error('无权限访问用户管理')
        return
      }
      throw new Error(`HTTP ${res.status}`)
    }
    const data = await res.json()
    if (data && data.success && Array.isArray(data.data)) {
      users.value = data.data
    } else {
      users.value = []
    }
  } catch (e) {
    console.error('加载用户失败:', e)
    ElMessage.error('加载用户列表失败：' + (e.message || '未知错误'))
    users.value = []
  }
}

// 打开新增弹窗
async function openAddDialog() {
  isEditing.value = false
  resetForm()
  showDialog.value = true
  // 清除之前的验证状态
  await nextTick()
  formRef.value?.clearValidate?.()
}

// 打开编辑弹窗
async function openEditDialog(user) {
  isEditing.value = true
  form.id = user.id
  form.username = user.username
  form.email = user.email || ''
  form.password = '' // 编辑时不显示旧密码，不填则不修改
  form.role_id = user.role_id || null
  form.phone = user.phone || ''
  
  showDialog.value = true
  // 清除之前的验证状态
  await nextTick()
  formRef.value?.clearValidate?.()
}

function resetForm() {
  form.id = null
  form.username = ''
  form.email = ''
  form.password = ''
  form.role_id = null
  form.phone = ''
  // reset validation if needed
  formRef.value?.clearValidate?.()
}

// 提交新增/编辑
async function submitForm() {
  // 验证表单（rules 已经是响应式的，会根据 isEditing 自动调整）
  try {
    await formRef.value.validate()
  } catch (error) {
    // 验证失败，不继续执行
    return
  }
  
  saving.value = true
  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token')
    const headers = {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
    
    if (isEditing.value) {
      // 编辑：PUT /auth/users/:id/ (不包含密码字段)
      const url = apiConfig.getUrl(apiConfig.endpoints.ADMIN.UPDATE_USER.replace('{id}', String(form.id)))
      const payload = {
        username: form.username,
        email: form.email,
        role_id: form.role_id,
        phone: form.phone
      }
      
      const res = await fetch(url, {
        method: 'PUT',
        headers,
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (!res.ok || !(data && data.success)) {
        // 处理验证错误
        let errorMsg = data.message || '保存失败'
        if (data.errors) {
          const errorDetails = Object.values(data.errors).flat().join('; ')
          if (errorDetails) {
            errorMsg += ': ' + errorDetails
          }
        }
        throw new Error(errorMsg)
      }
      ElMessage.success('用户已更新')
    } else {
      // 创建：POST /auth/users/
      const url = apiConfig.getUrl(apiConfig.endpoints.ADMIN.CREATE_USER)
      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          password: form.password,
          role_id: form.role_id,
          phone: form.phone
        })
      })
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}))
        throw new Error(errorData.message || `HTTP ${res.status}`)
      }
      const data = await res.json()
      if (!(data && data.success)) throw new Error(data.message || '创建失败')
      ElMessage.success('用户创建成功')
    }

    showDialog.value = false
    await loadUsers()
  } catch (e) {
    console.error('保存用户失败:', e)
    ElMessage.error('保存用户失败：' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

// 删除流程
function confirmDelete(user) {
  targetUser.value = user
  showDeleteConfirm.value = true
}

async function deleteUser() {
  if (!targetUser.value) return
  deleting.value = true
  try {
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token')
    const url = apiConfig.getUrl(apiConfig.endpoints.ADMIN.DELETE_USER.replace('{id}', String(targetUser.value.id)))
    const res = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    })
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.message || `HTTP ${res.status}`)
    }
    const data = await res.json()
    if (!(data && data.success)) throw new Error(data.message || '删除失败')
    ElMessage.success('用户已删除')
    showDeleteConfirm.value = false
    await loadUsers()
  } catch (e) {
    console.error('删除用户失败:', e)
    ElMessage.error('删除失败：' + (e.message || '未知错误'))
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  loadRoles()
  loadUsers()
})
</script>

<style scoped>
.admin-container {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}
.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.admin-header h2 {
  margin: 0;
  font-size: 18px;
}
.actions {
  display: flex;
  gap: 8px;
}
.admin-card {
  padding: 12px;
}
.empty-tip {
  padding: 20px;
  text-align: center;
  color: #909399;
}
</style>
