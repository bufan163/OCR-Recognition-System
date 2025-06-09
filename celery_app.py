from celery import Celery
from celery.schedules import crontab
from config import settings

# 创建Celery应用
celery_app = Celery(
    "ocr_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['tasks.ocr_tasks', 'tasks.cleanup_tasks']
)

# Celery配置
celery_app.conf.update(
    # 任务序列化
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 任务路由
    task_routes={
        'tasks.ocr_tasks.process_ocr_task': {'queue': 'ocr'},
        'tasks.cleanup_tasks.cleanup_old_files': {'queue': 'cleanup'},
        'tasks.cleanup_tasks.cleanup_failed_tasks': {'queue': 'cleanup'},
    },
    
    # 任务优先级
    task_default_priority=5,
    worker_prefetch_multiplier=1,
    
    # 任务超时
    task_soft_time_limit=300,  # 5分钟软超时
    task_time_limit=600,       # 10分钟硬超时
    
    # 任务重试
    task_acks_late=True,
    worker_disable_rate_limits=False,
    
    # 结果过期时间
    result_expires=3600,  # 1小时
    
    # 定时任务
    beat_schedule={
        # 每天凌晨2点清理旧文件
        'cleanup-old-files': {
            'task': 'tasks.cleanup_tasks.cleanup_old_files',
            'schedule': crontab(hour=2, minute=0),
        },
        # 每小时清理失败的任务
        'cleanup-failed-tasks': {
            'task': 'tasks.cleanup_tasks.cleanup_failed_tasks',
            'schedule': crontab(minute=0),
        },
        # 每天统计API使用情况
        'daily-usage-stats': {
            'task': 'tasks.stats_tasks.generate_daily_stats',
            'schedule': crontab(hour=1, minute=0),
        },
    },
)

# 队列配置
celery_app.conf.task_routes = {
    'tasks.ocr_tasks.*': {'queue': 'ocr'},
    'tasks.cleanup_tasks.*': {'queue': 'cleanup'},
    'tasks.stats_tasks.*': {'queue': 'stats'},
}

if __name__ == '__main__':
    celery_app.start()