import time
import io
import traceback
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.management import call_command
from predict.models import ForecastUpdateLog

# 配置最大重试次数（1次重试 = 总共运行2次）
MAX_RETRIES = 1


class Command(BaseCommand):
    help = '守护进程：监听数据库 ForecastUpdateLog 表，自动执行预测更新任务'

    def add_arguments(self, parser):
        # 1. 允许在启动守护进程时指定所有相关参数
        parser.add_argument(
            '--top_n',
            type=int,
            default=500,
            help='指定每次更新任务运行前多少条航线 (默认: 500)'
        )
        parser.add_argument(
            '--model_type',
            type=str,
            default=None,
            help='覆盖配置: 模型类型 (lgb/xgb)'
        )
        parser.add_argument(
            '--time_granularity',
            type=str,
            default=None,
            help='覆盖配置: 时间粒度 (monthly/quarterly/yearly)'
        )
        parser.add_argument(
            '--future_periods',
            type=int,
            default=None,
            help='覆盖配置: 预测时长'
        )
        parser.add_argument(
            '--max_workers',
            type=int,
            default=None,
            help='覆盖配置: 并行进程数'
        )

    def handle(self, *args, **options):
        # 2. 获取启动参数并保存到实例变量中
        self.top_n = options['top_n']
        self.model_type = options['model_type']
        self.time_granularity = options['time_granularity']
        self.future_periods = options['future_periods']
        self.max_workers = options['max_workers']

        # 生成配置描述字符串，用于日志显示
        config_desc = [f"Top {self.top_n}"]
        if self.model_type: config_desc.append(f"Model: {self.model_type}")
        if self.time_granularity: config_desc.append(f"Granularity: {self.time_granularity}")

        self.config_str = ", ".join(config_desc)

        self.stdout.write(self.style.SUCCESS(f"=== 预测任务守护进程已启动 ==="))
        self.stdout.write(self.style.SUCCESS(f"=== 当前运行配置: [{self.config_str}] (Ctrl+C 停止) ==="))

        while True:
            try:
                self.check_and_run()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"守护进程自身发生错误: {e}"))
                time.sleep(5)

            # 每隔 10 秒轮询一次数据库
            time.sleep(10)

    def check_and_run(self):
        last_task = ForecastUpdateLog.objects.first()

        if not last_task:
            return

        if last_task.status == 0:
            self.execute_task(last_task)

        elif last_task.status == 1:
            # 运行中，暂时跳过
            pass

        elif last_task.status == 3:
            self.handle_retry_logic(last_task)

    def execute_task(self, task):
        """执行具体的 update_forecasts 命令"""
        self.stdout.write(f"检测到新任务 (ID: {task.id})，准备执行...")

        # 1. 标记为运行中
        task.status = 1
        task.start_time = timezone.now()
        task.save()

        # 捕获输出流
        out_buffer = io.StringIO()
        err_buffer = io.StringIO()

        try:
            # === 核心：构建传递给 update_forecasts 的参数字典 ===
            cmd_kwargs = {
                'top_n': self.top_n,
                'stdout': out_buffer,
                'stderr': err_buffer,
            }

            # 只有当参数不为 None 时才传给子命令，否则让 update_forecasts 使用它自己的默认值
            if self.model_type:
                cmd_kwargs['model_type'] = self.model_type
            if self.time_granularity:
                cmd_kwargs['time_granularity'] = self.time_granularity
            if self.future_periods:
                cmd_kwargs['future_periods'] = self.future_periods
            if self.max_workers:
                cmd_kwargs['max_workers'] = self.max_workers

            # 调用子命令
            call_command('update_forecasts', **cmd_kwargs)

            # 2. 标记成功
            task.status = 2
            task.end_time = timezone.now()
            # 记录详细日志
            task.log_message = f"[Config: {self.config_str}]\n" + out_buffer.getvalue()
            task.save()
            self.stdout.write(self.style.SUCCESS(f"任务 (ID: {task.id}) 执行成功"))

        except Exception as e:
            # 3. 标记失败
            error_trace = traceback.format_exc()
            full_log = f"[Config: {self.config_str}]\n{out_buffer.getvalue()}\n\n=== ERROR ===\n{error_trace}"

            task.status = 3
            task.end_time = timezone.now()
            task.log_message = full_log
            task.save()
            self.stdout.write(self.style.ERROR(f"任务 (ID: {task.id}) 执行失败"))

        finally:
            out_buffer.close()
            err_buffer.close()

    def handle_retry_logic(self, failed_task):
        """
        判断是否满足重试条件
        """
        if failed_task.retry_count >= MAX_RETRIES:
            return

        existing_retry = ForecastUpdateLog.objects.filter(parent_task=failed_task).exists()
        if existing_retry:
            return

        self.stdout.write(
            self.style.WARNING(f"任务 (ID: {failed_task.id}) 失败，准备第 {failed_task.retry_count + 1} 次重试..."))

        ForecastUpdateLog.objects.create(
            status=0,
            retry_count=failed_task.retry_count + 1,
            parent_task=failed_task,
            log_message=f"自动重试：上一次失败任务ID为 {failed_task.id}"
        )