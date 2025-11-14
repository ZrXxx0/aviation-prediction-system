# 用户认证和权限管理系统

## 数据库初始化

### 1. 创建数据库迁移文件

```bash
cd backend
python manage.py makemigrations accounts
```

### 2. 执行数据库迁移

```bash
python manage.py migrate
```

### 3. 初始化角色数据

```bash
python manage.py init_roles
```

这将创建三个默认角色：
- **超级管理员** (super_admin): 拥有所有权限，包括用户管理
- **管理员** (admin): 可以查看数据看板、预测模块和数据管理，但不能管理用户
- **游客** (visitor): 只能查看数据看板

### 4. 创建超级管理员用户

可以通过Django admin后台创建，或者使用Django shell：

```bash
python manage.py shell
```

```python
from accounts.models import User, Role

# 获取超级管理员角色
super_admin_role = Role.objects.get(name='super_admin')

# 创建超级管理员用户
user = User.objects.create_user(
    username='admin',
    email='admin@example.com',
    password='your_password_here',
    role=super_admin_role
)
print(f"创建用户成功: {user.username}")
```

## API接口说明

### 认证相关

- `POST /auth/login/` - 用户登录
- `POST /auth/logout/` - 用户登出
- `GET /auth/user/info/` - 获取当前用户信息（需要认证）
- `GET /auth/roles/` - 获取所有角色列表（需要认证）

### 用户管理（需要超级管理员权限）

- `GET /auth/users/` - 获取用户列表
- `POST /auth/users/` - 创建用户
- `GET /auth/users/{id}/` - 获取用户详情
- `PUT /auth/users/{id}/` - 更新用户
- `DELETE /auth/users/{id}/` - 删除用户

## 权限说明

### 超级管理员 (super_admin)
- ✅ 查看数据看板
- ✅ 查看预测模块
- ✅ 查看数据管理
- ✅ 查看系统管理（用户管理）

### 管理员 (admin)
- ✅ 查看数据看板
- ✅ 查看预测模块
- ✅ 查看数据管理
- ❌ 查看系统管理

### 游客 (visitor)
- ✅ 查看数据看板
- ❌ 查看预测模块
- ❌ 查看数据管理
- ❌ 查看系统管理

## 前端使用

前端会根据用户角色自动显示/隐藏相应的菜单项和按钮：

1. **数据看板** - 所有用户可见
2. **预测模块** - 仅超级管理员和管理员可见
3. **数据管理** - 仅超级管理员和管理员可见
4. **系统管理按钮（齿轮图标）** - 仅超级管理员可见

## 注意事项

1. 所有需要认证的API请求都需要在Header中携带Token：
   ```
   Authorization: Bearer <token>
   ```

2. Token有效期为7天

3. 用户密码使用Django的密码加密机制存储

4. 删除用户时不能删除自己的账号

