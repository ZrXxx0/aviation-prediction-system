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
        <el-table-column label="角色/权限" width="260">
          <template #default="scope">
            <el-tag
              v-for="role in scope.row.roles"
              :key="scope.row.id + '-' + role"
              type="info"
              style="margin-right:6px;"
            >
              {{ role }}
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

        <el-form-item label="角色" prop="roles">
          <el-checkbox-group v-model="form.roles">
            <el-checkbox v-for="r in availableRoles" :key="r" :label="r">{{ r }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="说明">
          <el-input v-model="form.note" placeholder="可选：用户备注" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import apiConfig from '@/config/api.js'

const users = ref([])
const availableRoles = ref(['administrator', 'manager', 'viewer']) // 可扩展/从后端加载
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
  roles: [],
  note: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
  // password 在创建时必填
  password: [{ required: !isEditing.value, message: '请输入密码', trigger: 'blur' }]
}

// 加载用户列表
async function loadUsers() {
  try {
    // 使用 apiConfig 管理的端点（请在 api.js 中定义 ENDPOINTS.ADMIN.LIST_USERS）
    const url = apiConfig.getUrl?.(apiConfig.endpoints?.ADMIN?.LIST_USERS || '/admin/users/')
    const res = await fetch(url)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    // 假设后端返回 { success: true, data: { users: [...] } }
    if (data && data.success && Array.isArray(data.data?.users)) {
      users.value = data.data.users
    } else if (data && Array.isArray(data.users)) {
      // 兼容不同后端字段
      users.value = data.users
    } else {
      // 后端未实现，使用 mock
      users.value = [
        { id: 1, username: 'admin', email: 'admin@example.com', roles: ['administrator'], note: '超级管理员' },
        // { id: 2, username: 'alice', email: 'alice@example.com', roles: ['editor'], note: '' }
      ]
    }
  } catch (e) {
    console.error('加载用户失败:', e)
    ElMessage.warning('加载用户失败，已显示本地示例数据')
    users.value = [
      { id: 1, username: 'admin', email: 'admin@example.com', roles: ['administrator'], note: '超级管理员' },
    ]
  }
}

// 打开新增弹窗
function openAddDialog() {
  isEditing.value = false
  resetForm()
  showDialog.value = true
}

// 打开编辑弹窗
function openEditDialog(user) {
  isEditing.value = true
  form.id = user.id
  form.username = user.username
  form.email = user.email || ''
  form.password = '' // 不显示旧密码
  form.roles = Array.isArray(user.roles) ? [...user.roles] : []
  form.note = user.note || ''
  showDialog.value = true
}

function resetForm() {
  form.id = null
  form.username = ''
  form.email = ''
  form.password = ''
  form.roles = []
  form.note = ''
  // reset validation if needed
  formRef.value?.clearValidate?.()
}

// 提交新增/编辑
async function submitForm() {
  await formRef.value.validate().catch(() => { throw new Error('验证失败') })
  saving.value = true
  try {
    if (isEditing.value) {
      // 编辑：PUT /admin/users/:id/
      const endpoint = apiConfig.endpoints?.ADMIN?.UPDATE_USER || '/admin/users/{id}/'
      const url = apiConfig.getUrl?.(endpoint.replace('{id}', String(form.id))) || `/admin/users/${form.id}/`
      const res = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          roles: form.roles,
          note: form.note
        })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (!(data && data.success)) throw new Error('保存失败')
      ElMessage.success('用户已更新')
    } else {
      // 创建：POST /admin/users/
      const endpoint = apiConfig.endpoints?.ADMIN?.CREATE_USER || '/admin/users/'
      const url = apiConfig.getUrl?.(endpoint) || '/admin/users/'
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username,
          email: form.email,
          password: form.password,
          roles: form.roles,
          note: form.note
        })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      if (!(data && data.success)) throw new Error('创建失败')
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
    const endpoint = apiConfig.endpoints?.ADMIN?.DELETE_USER || '/admin/users/{id}/'
    const url = apiConfig.getUrl?.(endpoint.replace('{id}', String(targetUser.value.id))) || `/admin/users/${targetUser.value.id}/`
    const res = await fetch(url, { method: 'DELETE' })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (!(data && data.success)) throw new Error('删除失败')
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
