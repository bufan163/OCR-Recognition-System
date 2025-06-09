from celery import current_task
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from pathlib import Path
import os

from celery_app import celery_app
from database import get_db_session
from models import File, OCRTask, OCRResult, APIUsage
from utils.logger import setup_logger, log_system_event
from config import settings

logger = setup_logger("cleanup_tasks")


@celery_app.task
def cleanup_old_files(days: int = 30):
    """清理旧文件"""
    logger.info(f"开始清理 {days} 天前的文件")
    
    with get_db_session() as db:
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 查找过期文件
            old_files = db.query(File).filter(
                File.upload_time < cutoff_date,
                File.status.in_(["completed", "failed"])
            ).all()
            
            deleted_files = 0
            freed_space = 0
            
            for file_record in old_files:
                try:
                    # 删除磁盘文件
                    file_path = Path(file_record.file_path)
                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        freed_space += file_size
                    
                    # 删除相关的OCR结果
                    ocr_tasks = db.query(OCRTask).filter(OCRTask.file_id == file_record.id).all()
                    for task in ocr_tasks:
                        db.query(OCRResult).filter(OCRResult.task_id == task.id).delete()
                        db.delete(task)
                    
                    # 删除文件记录
                    db.delete(file_record)
                    deleted_files += 1
                    
                except Exception as e:
                    logger.error(f"删除文件失败: {file_record.id} - {e}")
                    continue
            
            db.commit()
            
            # 记录系统事件
            log_system_event(
                event="file_cleanup",
                details={
                    "deleted_files": deleted_files,
                    "freed_space_mb": round(freed_space / 1024 / 1024, 2),
                    "cutoff_days": days
                }
            )
            
            logger.info(f"文件清理完成: 删除 {deleted_files} 个文件, 释放 {freed_space / 1024 / 1024:.2f} MB")
            
            return {
                "status": "success",
                "deleted_files": deleted_files,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2)
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"文件清理失败: {e}")
            return {"status": "error", "message": str(e)}


@celery_app.task
def cleanup_failed_tasks(hours: int = 24):
    """清理失败的任务"""
    logger.info(f"开始清理 {hours} 小时前的失败任务")
    
    with get_db_session() as db:
        try:
            cutoff_date = datetime.now() - timedelta(hours=hours)
            
            # 查找失败的任务
            failed_tasks = db.query(OCRTask).filter(
                OCRTask.status == "failed",
                OCRTask.created_at < cutoff_date
            ).all()
            
            deleted_tasks = 0
            
            for task in failed_tasks:
                try:
                    # 删除OCR结果
                    db.query(OCRResult).filter(OCRResult.task_id == task.id).delete()
                    
                    # 删除任务记录
                    db.delete(task)
                    deleted_tasks += 1
                    
                except Exception as e:
                    logger.error(f"删除失败任务失败: {task.id} - {e}")
                    continue
            
            db.commit()
            
            # 记录系统事件
            log_system_event(
                event="failed_task_cleanup",
                details={
                    "deleted_tasks": deleted_tasks,
                    "cutoff_hours": hours
                }
            )
            
            logger.info(f"失败任务清理完成: 删除 {deleted_tasks} 个任务")
            
            return {
                "status": "success",
                "deleted_tasks": deleted_tasks
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"失败任务清理失败: {e}")
            return {"status": "error", "message": str(e)}


@celery_app.task
def cleanup_temp_files():
    """清理临时文件"""
    logger.info("开始清理临时文件")
    
    try:
        temp_dir = Path(settings.temp_dir)
        if not temp_dir.exists():
            return {"status": "success", "message": "临时目录不存在"}
        
        deleted_files = 0
        freed_space = 0
        cutoff_time = datetime.now() - timedelta(hours=1)  # 清理1小时前的临时文件
        
        for file_path in temp_dir.rglob("*"):
            if file_path.is_file():
                try:
                    # 检查文件修改时间
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        deleted_files += 1
                        freed_space += file_size
                except Exception as e:
                    logger.error(f"删除临时文件失败: {file_path} - {e}")
                    continue
        
        # 记录系统事件
        log_system_event(
            event="temp_file_cleanup",
            details={
                "deleted_files": deleted_files,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2)
            }
        )
        
        logger.info(f"临时文件清理完成: 删除 {deleted_files} 个文件, 释放 {freed_space / 1024 / 1024:.2f} MB")
        
        return {
            "status": "success",
            "deleted_files": deleted_files,
            "freed_space_mb": round(freed_space / 1024 / 1024, 2)
        }
        
    except Exception as e:
        logger.error(f"临时文件清理失败: {e}")
        return {"status": "error", "message": str(e)}


@celery_app.task
def cleanup_old_api_usage(days: int = 90):
    """清理旧的API使用记录"""
    logger.info(f"开始清理 {days} 天前的API使用记录")
    
    with get_db_session() as db:
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 删除旧的API使用记录
            deleted_count = db.query(APIUsage).filter(
                APIUsage.created_at < cutoff_date
            ).delete()
            
            db.commit()
            
            # 记录系统事件
            log_system_event(
                event="api_usage_cleanup",
                details={
                    "deleted_records": deleted_count,
                    "cutoff_days": days
                }
            )
            
            logger.info(f"API使用记录清理完成: 删除 {deleted_count} 条记录")
            
            return {
                "status": "success",
                "deleted_records": deleted_count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"API使用记录清理失败: {e}")
            return {"status": "error", "message": str(e)}


@celery_app.task
def cleanup_orphaned_files():
    """清理孤立文件（数据库中没有记录的文件）"""
    logger.info("开始清理孤立文件")
    
    with get_db_session() as db:
        try:
            upload_dir = Path(settings.upload_dir)
            if not upload_dir.exists():
                return {"status": "success", "message": "上传目录不存在"}
            
            # 获取数据库中所有文件路径
            db_file_paths = set()
            files = db.query(File.file_path).all()
            for file_record in files:
                db_file_paths.add(Path(file_record.file_path))
            
            deleted_files = 0
            freed_space = 0
            
            # 遍历上传目录中的所有文件
            for file_path in upload_dir.rglob("*"):
                if file_path.is_file():
                    if file_path not in db_file_paths:
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            deleted_files += 1
                            freed_space += file_size
                        except Exception as e:
                            logger.error(f"删除孤立文件失败: {file_path} - {e}")
                            continue
            
            # 记录系统事件
            log_system_event(
                event="orphaned_file_cleanup",
                details={
                    "deleted_files": deleted_files,
                    "freed_space_mb": round(freed_space / 1024 / 1024, 2)
                }
            )
            
            logger.info(f"孤立文件清理完成: 删除 {deleted_files} 个文件, 释放 {freed_space / 1024 / 1024:.2f} MB")
            
            return {
                "status": "success",
                "deleted_files": deleted_files,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2)
            }
            
        except Exception as e:
            logger.error(f"孤立文件清理失败: {e}")
            return {"status": "error", "message": str(e)}


@celery_app.task
def cleanup_stuck_tasks(hours: int = 2):
    """清理卡住的任务"""
    logger.info(f"开始清理卡住超过 {hours} 小时的任务")
    
    with get_db_session() as db:
        try:
            cutoff_date = datetime.now() - timedelta(hours=hours)
            
            # 查找卡住的任务（状态为processing但很久没有更新）
            stuck_tasks = db.query(OCRTask).filter(
                OCRTask.status == "processing",
                OCRTask.started_at < cutoff_date
            ).all()
            
            reset_tasks = 0
            
            for task in stuck_tasks:
                try:
                    # 取消Celery任务
                    if task.celery_task_id:
                        celery_app.control.revoke(task.celery_task_id, terminate=True)
                    
                    # 重置任务状态
                    task.status = "failed"
                    task.error_message = "任务超时被系统重置"
                    task.completed_at = datetime.now()
                    
                    reset_tasks += 1
                    
                except Exception as e:
                    logger.error(f"重置卡住任务失败: {task.id} - {e}")
                    continue
            
            db.commit()
            
            # 记录系统事件
            log_system_event(
                event="stuck_task_cleanup",
                details={
                    "reset_tasks": reset_tasks,
                    "cutoff_hours": hours
                }
            )
            
            logger.info(f"卡住任务清理完成: 重置 {reset_tasks} 个任务")
            
            return {
                "status": "success",
                "reset_tasks": reset_tasks
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"卡住任务清理失败: {e}")
            return {"status": "error", "message": str(e)}


@celery_app.task
def full_cleanup():
    """执行完整清理"""
    logger.info("开始执行完整清理")
    
    results = {}
    
    # 清理旧文件
    results["old_files"] = cleanup_old_files.delay(30).get()
    
    # 清理失败任务
    results["failed_tasks"] = cleanup_failed_tasks.delay(24).get()
    
    # 清理临时文件
    results["temp_files"] = cleanup_temp_files.delay().get()
    
    # 清理API使用记录
    results["api_usage"] = cleanup_old_api_usage.delay(90).get()
    
    # 清理孤立文件
    results["orphaned_files"] = cleanup_orphaned_files.delay().get()
    
    # 清理卡住的任务
    results["stuck_tasks"] = cleanup_stuck_tasks.delay(2).get()
    
    # 记录系统事件
    log_system_event(
        event="full_cleanup_completed",
        details=results
    )
    
    logger.info("完整清理执行完成")
    
    return {
        "status": "success",
        "results": results
    }