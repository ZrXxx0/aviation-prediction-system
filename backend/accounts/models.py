from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class Role(models.Model):
    """角色表"""
    ROLE_CHOICES = [
        ('super_admin', '超级管理员'),
        ('admin', '管理员'),
        ('visitor', '游客'),
    ]
    
    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True, verbose_name='角色名称')
    display_name = models.CharField(max_length=50, verbose_name='显示名称')
    description = models.TextField(blank=True, verbose_name='角色描述')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'role'
        verbose_name = '角色'
        verbose_name_plural = '角色'
        ordering = ['id']
    
    def __str__(self):
        return self.display_name


class User(AbstractUser):
    """用户表 - 扩展Django默认User模型"""
    email = models.EmailField(unique=True, verbose_name='邮箱')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, 
                            related_name='users', verbose_name='角色')
    phone = models.CharField(max_length=20, blank=True, verbose_name='手机号')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    last_login = models.DateTimeField(null=True, blank=True, verbose_name='最后登录时间')
    
    # 使用email作为用户名
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        db_table = 'user'
        verbose_name = '用户'
        verbose_name_plural = '用户'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    def get_role_name(self):
        """获取角色名称"""
        return self.role.name if self.role else None
    
    def has_permission(self, permission):
        """检查用户是否有特定权限"""
        if not self.role:
            return False
        
        role_name = self.role.name
        
        # 权限定义
        permissions = {
            'super_admin': ['view_dashboard', 'view_forecast', 'view_management', 'view_administration'],
            'admin': ['view_dashboard', 'view_forecast', 'view_management'],
            'visitor': ['view_dashboard'],
        }
        
        return permission in permissions.get(role_name, [])
    
    def can_view_administration(self):
        """是否可以查看系统管理"""
        return self.role and self.role.name == 'super_admin'
    
    def can_view_forecast(self):
        """是否可以查看预测模块"""
        return self.role and self.role.name in ['super_admin', 'admin']
    
    def can_view_management(self):
        """是否可以查看数据管理"""
        return self.role and self.role.name in ['super_admin', 'admin']
