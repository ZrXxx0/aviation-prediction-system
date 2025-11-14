from django.core.management.base import BaseCommand
from accounts.models import Role


class Command(BaseCommand):
    help = '初始化角色数据'

    def handle(self, *args, **options):
        roles_data = [
            {
                'name': 'super_admin',
                'display_name': '超级管理员',
                'description': '拥有所有权限，包括用户管理'
            },
            {
                'name': 'admin',
                'display_name': '管理员',
                'description': '可以查看数据看板、预测模块和数据管理，但不能管理用户'
            },
            {
                'name': 'visitor',
                'display_name': '游客',
                'description': '只能查看数据看板'
            },
        ]
        
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'成功创建角色: {role.display_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'角色已存在: {role.display_name}')
                )

