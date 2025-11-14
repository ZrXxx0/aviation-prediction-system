import jwt
from datetime import datetime, timedelta
from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.utils import ProgrammingError, IntegrityError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import User, Role
from .serializers import (
    UserSerializer, UserListSerializer, LoginSerializer, 
    UserInfoSerializer, RoleSerializer
)


def generate_token(user):
    """生成JWT token"""
    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(days=7),  # 7天过期
        'iat': datetime.utcnow()
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def login(request):
    """用户登录"""
    try:
        # 检查请求数据格式
        if not request.data:
            return Response({
                'success': False,
                'message': '请求数据为空，请提供 email 和 password',
                'errors': {'detail': '请求体不能为空'}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '请求参数错误',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'success': False,
                'message': '用户不存在或密码错误'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # 验证密码
        if not user.check_password(password):
            return Response({
                'success': False,
                'message': '用户不存在或密码错误'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # 检查用户是否激活
        if not user.is_active:
            return Response({
                'success': False,
                'message': '用户已被禁用，请联系管理员'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # 更新最后登录时间
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # 生成token
        token = generate_token(user)
        
        # 获取用户信息
        user_info = UserInfoSerializer(user).data
        
        return Response({
            'success': True,
            'message': '登录成功',
            'data': {
                'token': token,
                'user': user_info
            }
        })
    except Exception as e:
        # 捕获所有异常，返回友好的错误信息
        import traceback
        print(f"登录异常: {str(e)}")
        print(traceback.format_exc())
        return Response({
            'success': False,
            'message': f'登录失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_info(request):
    """获取当前用户信息"""
    user = request.user
    user_info = UserInfoSerializer(user).data
    
    return Response({
        'success': True,
        'data': user_info
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_roles(request):
    """获取所有角色列表"""
    roles = Role.objects.all()
    serializer = RoleSerializer(roles, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_list(request):
    """用户列表和创建用户"""
    # 检查权限：只有超级管理员可以管理用户
    if not request.user.can_view_administration():
        return Response({
            'success': False,
            'message': '无权限访问'
        }, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        # 获取用户列表
        users = User.objects.all().select_related('role')
        serializer = UserListSerializer(users, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'POST':
        # 创建用户
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': '用户创建成功',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': '创建失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def user_detail(request, user_id):
    """用户详情、更新和删除"""
    # 检查权限：只有超级管理员可以管理用户
    if not request.user.can_view_administration():
        return Response({
            'success': False,
            'message': '无权限访问'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': '用户不存在'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response({
            'success': True,
            'data': serializer.data
        })
    
    elif request.method == 'PUT':
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'success': True,
                'message': '用户更新成功',
                'data': serializer.data
            })
        
        return Response({
            'success': False,
            'message': '更新失败',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        # 不能删除自己
        if user.id == request.user.id:
            return Response({
                'success': False,
                'message': '不能删除自己的账号'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 尝试删除用户
            # 使用 bulk=False 来避免级联删除时的问题
            with transaction.atomic():
                # 先清理可能存在的关联记录（如果表存在）
                try:
                    # 尝试清理 admin_log 记录（如果表存在）
                    from django.contrib.admin.models import LogEntry
                    LogEntry.objects.filter(user_id=user.id).delete()
                except (ProgrammingError, Exception):
                    # 如果表不存在或清理失败，忽略错误继续删除用户
                    pass
                
                # 删除用户
                user.delete()
            
            return Response({
                'success': True,
                'message': '用户删除成功'
            })
        except ProgrammingError as e:
            # 处理数据库表不存在的错误
            import traceback
            print(f"删除用户时数据库错误: {str(e)}")
            print(traceback.format_exc())
            
            # 尝试直接删除用户（忽略关联表）
            try:
                # 使用原始SQL删除，避免Django的级联删除机制
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM `user` WHERE id = %s", [user.id])
                
                return Response({
                    'success': True,
                    'message': '用户删除成功'
                })
            except Exception as e2:
                return Response({
                    'success': False,
                    'message': f'删除用户失败: {str(e2)}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except IntegrityError as e:
            # 处理外键约束错误
            return Response({
                'success': False,
                'message': '无法删除用户：该用户存在关联数据，请先清理相关数据'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # 处理其他异常
            import traceback
            print(f"删除用户异常: {str(e)}")
            print(traceback.format_exc())
            return Response({
                'success': False,
                'message': f'删除用户失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """用户登出（前端删除token即可，这里只是接口占位）"""
    return Response({
        'success': True,
        'message': '登出成功'
    })
