from django.core.management.base import BaseCommand
from accounts.models import User, Role


class Command(BaseCommand):
    help = '创建测试用户（超级管理员、管理员、游客）'

    def handle(self, *args, **options):
        # 获取角色
        super_admin_role = Role.objects.get(name='super_admin')
        admin_role = Role.objects.get(name='admin')
        visitor_role = Role.objects.get(name='visitor')
        
        # 测试用户数据
        users_data = [
            {
                'username': 'superadmin',
                'email': 'superadmin@test.com',
                'password': 'superadmin123',
                'role': super_admin_role,
                'phone': '13800000001',
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'admin',
                'email': 'admin@test.com',
                'password': 'admin123',
                'role': admin_role,
                'phone': '13800000002',
                'is_staff': True,
                'is_superuser': False,
            },
            {
                'username': 'visitor',
                'email': 'visitor@test.com',
                'password': 'visitor123',
                'role': visitor_role,
                'phone': '13800000003',
                'is_staff': False,
                'is_superuser': False,
            },
        ]
        
        for user_data in users_data:
            email = user_data.pop('email')
            password = user_data.pop('password')
            
            user, created = User.objects.get_or_create(
                email=email,
                defaults=user_data
            )
            
            if created:
                # 设置密码
                user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'成功创建用户: {user.username} ({user.email}) - 角色: {user.role.display_name}'
                    )
                )
            else:
                # 如果用户已存在，更新密码和角色
                user.set_password(password)
                for key, value in user_data.items():
                    setattr(user, key, value)
                user.save()
                self.stdout.write(
                    self.style.WARNING(
                        f'用户已存在，已更新: {user.username} ({user.email}) - 角色: {user.role.display_name}'
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS('\n所有测试用户创建完成！')
        )
        self.stdout.write(
            self.style.SUCCESS('\n登录信息：')
        )
        self.stdout.write(
            self.style.SUCCESS('1. 超级管理员 - 邮箱: superadmin@test.com, 密码: superadmin123')
        )
        self.stdout.write(
            self.style.SUCCESS('2. 管理员 - 邮箱: admin@test.com, 密码: admin123')
        )
        self.stdout.write(
            self.style.SUCCESS('3. 游客 - 邮箱: visitor@test.com, 密码: visitor123')
        )

