from rest_framework import serializers
from .models import User, Role


class RoleSerializer(serializers.ModelSerializer):
    """角色序列化器"""
    class Meta:
        model = Role
        fields = ['id', 'name', 'display_name', 'description']


class UserSerializer(serializers.ModelSerializer):
    """用户序列化器"""
    role = RoleSerializer(read_only=True)
    role_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'role_id', 'phone', 
                 'is_active', 'created_at', 'last_login']
        read_only_fields = ['id', 'created_at', 'last_login']
    
    def validate_email(self, value):
        """验证邮箱唯一性"""
        # 如果是更新操作，排除当前用户
        if self.instance:
            if User.objects.filter(email=value).exclude(id=self.instance.id).exists():
                raise serializers.ValidationError("该邮箱已被使用")
        else:
            # 创建操作
            if User.objects.filter(email=value).exists():
                raise serializers.ValidationError("该邮箱已被使用")
        return value
    
    def create(self, validated_data):
        """创建用户"""
        role_id = validated_data.pop('role_id', None)
        password = validated_data.pop('password', None)
        
        user = User.objects.create(**validated_data)
        if password:
            user.set_password(password)
        if role_id:
            try:
                role = Role.objects.get(id=role_id)
                user.role = role
            except Role.DoesNotExist:
                pass
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """更新用户"""
        role_id = validated_data.pop('role_id', None)
        password = validated_data.pop('password', None)
        
        # 更新基本字段
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # 更新密码（如果提供了）
        if password and password.strip():
            instance.set_password(password)
        
        # 更新角色
        if role_id is not None:
            try:
                role = Role.objects.get(id=role_id)
                instance.role = role
            except Role.DoesNotExist:
                instance.role = None
        
        instance.save()
        return instance


class UserListSerializer(serializers.ModelSerializer):
    """用户列表序列化器（简化版）"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_display = serializers.CharField(source='role.display_name', read_only=True)
    role_id = serializers.IntegerField(source='role.id', read_only=True)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role_name', 'role_display', 'role_id', 'phone', 
                 'is_active', 'created_at', 'last_login']


class LoginSerializer(serializers.Serializer):
    """登录序列化器"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class UserInfoSerializer(serializers.ModelSerializer):
    """用户信息序列化器（用于返回给前端）"""
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_display = serializers.CharField(source='role.display_name', read_only=True)
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role_name', 'role_display', 
                 'permissions', 'phone', 'is_active']
    
    def get_permissions(self, obj):
        """获取用户权限列表"""
        if not obj.role:
            return []
        
        role_name = obj.role.name
        permissions = {
            'super_admin': ['view_dashboard', 'view_forecast', 'view_management', 'view_administration'],
            'admin': ['view_dashboard', 'view_forecast', 'view_management'],
            'visitor': ['view_dashboard'],
        }
        return permissions.get(role_name, [])

