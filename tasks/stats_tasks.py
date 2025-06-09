from celery import current_task
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json

from celery_app import celery_app
from database import get_db_session
from models import User, File, OCRTask, OCRResult, APIUsage, UserQuota
from utils.logger import setup_logger, log_system_event
from config import settings, OCR_ENGINE_COSTS

logger = setup_logger("stats_tasks")


@celery_app.task
def generate_daily_stats(date: str = None):
    """生成每日统计报告"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now().date()
    
    logger.info(f"生成 {target_date} 的每日统计报告")
    
    with get_db_session() as db:
        try:
            start_time = datetime.combine(target_date, datetime.min.time())
            end_time = datetime.combine(target_date, datetime.max.time())
            
            # 用户统计
            user_stats = _get_user_stats(db, start_time, end_time)
            
            # 文件统计
            file_stats = _get_file_stats(db, start_time, end_time)
            
            # OCR任务统计
            task_stats = _get_task_stats(db, start_time, end_time)
            
            # API使用统计
            api_stats = _get_api_usage_stats(db, start_time, end_time)
            
            # 引擎性能统计
            engine_stats = _get_engine_performance_stats(db, start_time, end_time)
            
            # 系统资源统计
            system_stats = _get_system_stats(db, start_time, end_time)
            
            daily_report = {
                "date": target_date.isoformat(),
                "user_stats": user_stats,
                "file_stats": file_stats,
                "task_stats": task_stats,
                "api_stats": api_stats,
                "engine_stats": engine_stats,
                "system_stats": system_stats,
                "generated_at": datetime.now().isoformat()
            }
            
            # 记录系统事件
            log_system_event(
                event="daily_stats_generated",
                details={
                    "date": target_date.isoformat(),
                    "total_users": user_stats["total_active_users"],
                    "total_files": file_stats["total_files_uploaded"],
                    "total_tasks": task_stats["total_tasks_created"]
                }
            )
            
            logger.info(f"每日统计报告生成完成: {target_date}")
            
            return daily_report
            
        except Exception as e:
            logger.error(f"生成每日统计报告失败: {e}")
            return {"status": "error", "message": str(e)}


def _get_user_stats(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """获取用户统计"""
    # 新注册用户
    new_users = db.query(User).filter(
        and_(User.created_at >= start_time, User.created_at <= end_time)
    ).count()
    
    # 活跃用户（当天有操作的用户）
    active_users = db.query(func.distinct(OCRTask.user_id)).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time)
    ).count()
    
    # 总用户数
    total_users = db.query(User).count()
    
    # 用户计划分布
    plan_distribution = db.query(
        User.plan,
        func.count(User.id).label('count')
    ).group_by(User.plan).all()
    
    return {
        "new_users": new_users,
        "total_active_users": active_users,
        "total_users": total_users,
        "plan_distribution": {plan: count for plan, count in plan_distribution}
    }


def _get_file_stats(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """获取文件统计"""
    # 上传文件数
    total_files = db.query(File).filter(
        and_(File.upload_time >= start_time, File.upload_time <= end_time)
    ).count()
    
    # 文件类型分布
    file_type_stats = db.query(
        File.file_type,
        func.count(File.id).label('count'),
        func.sum(File.file_size).label('total_size')
    ).filter(
        and_(File.upload_time >= start_time, File.upload_time <= end_time)
    ).group_by(File.file_type).all()
    
    # 文件状态分布
    status_stats = db.query(
        File.status,
        func.count(File.id).label('count')
    ).filter(
        and_(File.upload_time >= start_time, File.upload_time <= end_time)
    ).group_by(File.status).all()
    
    # 总存储使用量
    total_storage = db.query(func.sum(File.file_size)).filter(
        and_(File.upload_time >= start_time, File.upload_time <= end_time)
    ).scalar() or 0
    
    return {
        "total_files_uploaded": total_files,
        "total_storage_bytes": total_storage,
        "total_storage_mb": round(total_storage / 1024 / 1024, 2),
        "file_type_distribution": {
            file_type: {
                "count": count,
                "total_size_mb": round(total_size / 1024 / 1024, 2) if total_size else 0
            }
            for file_type, count, total_size in file_type_stats
        },
        "status_distribution": {status: count for status, count in status_stats}
    }


def _get_task_stats(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """获取OCR任务统计"""
    # 任务总数
    total_tasks = db.query(OCRTask).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time)
    ).count()
    
    # 任务状态分布
    status_stats = db.query(
        OCRTask.status,
        func.count(OCRTask.id).label('count')
    ).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time)
    ).group_by(OCRTask.status).all()
    
    # 引擎使用分布
    engine_stats = db.query(
        OCRTask.engine_used,
        func.count(OCRTask.id).label('count')
    ).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time),
        OCRTask.engine_used.isnot(None)
    ).group_by(OCRTask.engine_used).all()
    
    # 平均处理时间
    completed_tasks = db.query(OCRTask).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time),
        OCRTask.status == "completed",
        OCRTask.started_at.isnot(None),
        OCRTask.completed_at.isnot(None)
    ).all()
    
    processing_times = []
    for task in completed_tasks:
        if task.started_at and task.completed_at:
            duration = (task.completed_at - task.started_at).total_seconds()
            processing_times.append(duration)
    
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    # 总页数处理
    total_pages = db.query(func.sum(OCRTask.processed_pages)).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time)
    ).scalar() or 0
    
    return {
        "total_tasks_created": total_tasks,
        "total_pages_processed": total_pages,
        "avg_processing_time_seconds": round(avg_processing_time, 2),
        "status_distribution": {status: count for status, count in status_stats},
        "engine_distribution": {engine: count for engine, count in engine_stats}
    }


def _get_api_usage_stats(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """获取API使用统计"""
    # API调用统计
    api_calls = db.query(
        APIUsage.engine,
        func.count(APIUsage.id).label('calls'),
        func.sum(APIUsage.pages_processed).label('total_pages'),
        func.sum(APIUsage.cost).label('total_cost')
    ).filter(
        and_(APIUsage.created_at >= start_time, APIUsage.created_at <= end_time)
    ).group_by(APIUsage.engine).all()
    
    # 总成本
    total_cost = db.query(func.sum(APIUsage.cost)).filter(
        and_(APIUsage.created_at >= start_time, APIUsage.created_at <= end_time)
    ).scalar() or 0
    
    # 用户成本排行
    user_costs = db.query(
        APIUsage.user_id,
        func.sum(APIUsage.cost).label('total_cost')
    ).filter(
        and_(APIUsage.created_at >= start_time, APIUsage.created_at <= end_time)
    ).group_by(APIUsage.user_id).order_by(func.sum(APIUsage.cost).desc()).limit(10).all()
    
    return {
        "total_cost": round(total_cost, 4),
        "engine_usage": {
            engine: {
                "calls": calls,
                "pages": total_pages,
                "cost": round(total_cost, 4)
            }
            for engine, calls, total_pages, total_cost in api_calls
        },
        "top_users_by_cost": [
            {"user_id": user_id, "cost": round(cost, 4)}
            for user_id, cost in user_costs
        ]
    }


def _get_engine_performance_stats(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """获取引擎性能统计"""
    # 按引擎统计成功率和平均置信度
    engine_performance = {}
    
    engines = db.query(func.distinct(OCRTask.engine_used)).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time),
        OCRTask.engine_used.isnot(None)
    ).all()
    
    for (engine,) in engines:
        # 该引擎的所有任务
        engine_tasks = db.query(OCRTask).filter(
            and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time),
            OCRTask.engine_used == engine
        ).all()
        
        total_tasks = len(engine_tasks)
        completed_tasks = len([t for t in engine_tasks if t.status == "completed"])
        failed_tasks = len([t for t in engine_tasks if t.status == "failed"])
        
        # 平均置信度
        confidence_scores = [t.confidence_score for t in engine_tasks if t.confidence_score is not None]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        # 成功率
        success_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        engine_performance[engine] = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "success_rate_percent": round(success_rate, 2),
            "avg_confidence": round(avg_confidence, 4)
        }
    
    return engine_performance


def _get_system_stats(db: Session, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
    """获取系统统计"""
    # 错误统计
    error_tasks = db.query(OCRTask).filter(
        and_(OCRTask.created_at >= start_time, OCRTask.created_at <= end_time),
        OCRTask.status == "failed"
    ).all()
    
    error_messages = {}
    for task in error_tasks:
        if task.error_message:
            error_type = task.error_message.split(':')[0] if ':' in task.error_message else task.error_message
            error_messages[error_type] = error_messages.get(error_type, 0) + 1
    
    # 系统负载（基于任务队列）
    pending_tasks = db.query(OCRTask).filter(OCRTask.status == "pending").count()
    processing_tasks = db.query(OCRTask).filter(OCRTask.status == "processing").count()
    
    return {
        "error_distribution": error_messages,
        "current_pending_tasks": pending_tasks,
        "current_processing_tasks": processing_tasks,
        "system_load": pending_tasks + processing_tasks
    }


@celery_app.task
def generate_weekly_report(week_start: str = None):
    """生成周报"""
    if week_start:
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    else:
        # 获取本周一
        today = datetime.now().date()
        start_date = today - timedelta(days=today.weekday())
    
    end_date = start_date + timedelta(days=6)
    
    logger.info(f"生成 {start_date} 到 {end_date} 的周报")
    
    # 收集每日数据
    daily_reports = []
    current_date = start_date
    
    while current_date <= end_date:
        daily_report = generate_daily_stats.delay(current_date.isoformat()).get()
        daily_reports.append(daily_report)
        current_date += timedelta(days=1)
    
    # 汇总周数据
    weekly_summary = _aggregate_weekly_data(daily_reports)
    
    weekly_report = {
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "daily_reports": daily_reports,
        "weekly_summary": weekly_summary,
        "generated_at": datetime.now().isoformat()
    }
    
    # 记录系统事件
    log_system_event(
        event="weekly_report_generated",
        details={
            "week_start": start_date.isoformat(),
            "week_end": end_date.isoformat(),
            "total_users": weekly_summary["total_active_users"],
            "total_tasks": weekly_summary["total_tasks"]
        }
    )
    
    logger.info(f"周报生成完成: {start_date} - {end_date}")
    
    return weekly_report


def _aggregate_weekly_data(daily_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总周数据"""
    summary = {
        "total_new_users": 0,
        "total_active_users": 0,
        "total_files_uploaded": 0,
        "total_storage_mb": 0,
        "total_tasks": 0,
        "total_pages_processed": 0,
        "total_cost": 0,
        "avg_success_rate": 0,
        "engine_usage": {},
        "daily_trends": []
    }
    
    valid_reports = [r for r in daily_reports if "user_stats" in r]
    
    if not valid_reports:
        return summary
    
    # 汇总数据
    for report in valid_reports:
        summary["total_new_users"] += report["user_stats"].get("new_users", 0)
        summary["total_active_users"] += report["user_stats"].get("total_active_users", 0)
        summary["total_files_uploaded"] += report["file_stats"].get("total_files_uploaded", 0)
        summary["total_storage_mb"] += report["file_stats"].get("total_storage_mb", 0)
        summary["total_tasks"] += report["task_stats"].get("total_tasks_created", 0)
        summary["total_pages_processed"] += report["task_stats"].get("total_pages_processed", 0)
        summary["total_cost"] += report["api_stats"].get("total_cost", 0)
        
        # 引擎使用汇总
        for engine, data in report["task_stats"].get("engine_distribution", {}).items():
            if engine not in summary["engine_usage"]:
                summary["engine_usage"][engine] = 0
            summary["engine_usage"][engine] += data
        
        # 每日趋势
        summary["daily_trends"].append({
            "date": report["date"],
            "active_users": report["user_stats"].get("total_active_users", 0),
            "files_uploaded": report["file_stats"].get("total_files_uploaded", 0),
            "tasks_created": report["task_stats"].get("total_tasks_created", 0)
        })
    
    # 计算平均值
    summary["avg_active_users_per_day"] = summary["total_active_users"] / len(valid_reports)
    summary["total_cost"] = round(summary["total_cost"], 4)
    summary["total_storage_mb"] = round(summary["total_storage_mb"], 2)
    
    return summary


@celery_app.task
def generate_monthly_report(month: str = None):
    """生成月报"""
    if month:
        target_month = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    else:
        target_month = datetime.now().date().replace(day=1)
    
    # 计算月份的最后一天
    if target_month.month == 12:
        next_month = target_month.replace(year=target_month.year + 1, month=1)
    else:
        next_month = target_month.replace(month=target_month.month + 1)
    
    end_date = next_month - timedelta(days=1)
    
    logger.info(f"生成 {target_month} 的月报")
    
    with get_db_session() as db:
        start_time = datetime.combine(target_month, datetime.min.time())
        end_time = datetime.combine(end_date, datetime.max.time())
        
        # 生成月度统计
        monthly_stats = {
            "month": target_month.strftime("%Y-%m"),
            "user_stats": _get_user_stats(db, start_time, end_time),
            "file_stats": _get_file_stats(db, start_time, end_time),
            "task_stats": _get_task_stats(db, start_time, end_time),
            "api_stats": _get_api_usage_stats(db, start_time, end_time),
            "engine_stats": _get_engine_performance_stats(db, start_time, end_time),
            "system_stats": _get_system_stats(db, start_time, end_time),
            "generated_at": datetime.now().isoformat()
        }
        
        # 记录系统事件
        log_system_event(
            event="monthly_report_generated",
            details={
                "month": target_month.strftime("%Y-%m"),
                "total_users": monthly_stats["user_stats"]["total_active_users"],
                "total_tasks": monthly_stats["task_stats"]["total_tasks_created"]
            }
        )
        
        logger.info(f"月报生成完成: {target_month.strftime('%Y-%m')}")
        
        return monthly_stats


@celery_app.task
def update_user_quotas():
    """更新用户配额"""
    logger.info("开始更新用户配额")
    
    with get_db_session() as db:
        try:
            # 获取所有用户配额
            quotas = db.query(UserQuota).all()
            updated_count = 0
            
            for quota in quotas:
                # 重置每日配额（如果是新的一天）
                if quota.last_reset_date != datetime.now().date():
                    quota.daily_pages_used = 0
                    quota.last_reset_date = datetime.now().date()
                    updated_count += 1
                
                # 重置每月配额（如果是新的月份）
                current_month = datetime.now().date().replace(day=1)
                if quota.monthly_reset_date != current_month:
                    quota.monthly_pages_used = 0
                    quota.monthly_reset_date = current_month
                    updated_count += 1
            
            db.commit()
            
            logger.info(f"用户配额更新完成: 更新了 {updated_count} 个配额")
            
            return {
                "status": "success",
                "updated_quotas": updated_count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"更新用户配额失败: {e}")
            return {"status": "error", "message": str(e)}