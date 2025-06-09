from celery import current_task
from celery.exceptions import Retry
from sqlalchemy.orm import Session
from datetime import datetime
import asyncio
import traceback

from celery_app import celery_app
from database import get_db_session
from models import OCRTask, OCRResult, File, APIUsage
from services.ocr_service import OCRService
from utils.logger import setup_logger, log_performance, log_user_activity
from config import settings

logger = setup_logger("ocr_tasks")
ocr_service = OCRService()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_ocr_task(self, task_id: int, engine_preference: str = None):
    """处理OCR任务"""
    start_time = datetime.now()
    
    with get_db_session() as db:
        try:
            # 获取任务信息
            task = db.query(OCRTask).filter(OCRTask.id == task_id).first()
            if not task:
                logger.error(f"任务不存在: {task_id}")
                return {"status": "error", "message": "任务不存在"}
            
            # 检查任务状态
            if task.status != "pending":
                logger.warning(f"任务状态不正确: {task_id} - {task.status}")
                return {"status": "error", "message": "任务状态不正确"}
            
            # 更新任务状态
            task.status = "processing"
            task.started_at = datetime.now()
            task.celery_task_id = self.request.id
            db.commit()
            
            # 获取文件信息
            file_record = db.query(File).filter(File.id == task.file_id).first()
            if not file_record:
                raise ValueError("关联文件不存在")
            
            # 更新任务进度
            self.update_state(
                state='PROGRESS',
                meta={'current': 0, 'total': 1, 'status': '开始处理文件'}
            )
            
            # 异步处理OCR
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    _process_file_ocr(db, task, file_record, engine_preference, self)
                )
            finally:
                loop.close()
            
            # 记录性能日志
            processing_time = (datetime.now() - start_time).total_seconds()
            log_performance(
                operation="ocr_task_processing",
                duration=processing_time,
                details={
                    "task_id": task_id,
                    "engine": task.engine_used,
                    "pages": task.total_pages,
                    "file_type": file_record.file_type
                }
            )
            
            # 记录用户活动
            log_user_activity(
                user_id=task.user_id,
                activity="ocr_completed",
                details={
                    "task_id": task_id,
                    "file_id": task.file_id,
                    "pages_processed": task.processed_pages,
                    "processing_time": processing_time
                }
            )
            
            logger.info(f"OCR任务完成: {task_id}, 耗时: {processing_time:.2f}s")
            
            return {
                "status": "completed",
                "task_id": task_id,
                "pages_processed": task.processed_pages,
                "processing_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"OCR任务处理失败: {task_id} - {e}")
            logger.error(traceback.format_exc())
            
            # 更新任务状态为失败
            task = db.query(OCRTask).filter(OCRTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.completed_at = datetime.now()
                db.commit()
            
            # 重试逻辑
            if self.request.retries < self.max_retries:
                logger.info(f"任务重试: {task_id}, 重试次数: {self.request.retries + 1}")
                raise self.retry(countdown=60 * (2 ** self.request.retries))
            
            return {
                "status": "failed",
                "task_id": task_id,
                "error": str(e)
            }


async def _process_file_ocr(db: Session, task: OCRTask, file_record: File, engine_preference: str, celery_task):
    """处理文件OCR的核心逻辑"""
    try:
        # 提取图像
        celery_task.update_state(
            state='PROGRESS',
            meta={'current': 1, 'total': 4, 'status': '提取图像中...'}
        )
        
        if file_record.file_type == 'pdf':
            images = ocr_service._extract_images_from_pdf(file_record.file_path)
        else:
            from PIL import Image
            image = Image.open(file_record.file_path)
            images = [image]
        
        task.total_pages = len(images)
        db.commit()
        
        # 选择OCR引擎
        celery_task.update_state(
            state='PROGRESS',
            meta={'current': 2, 'total': 4, 'status': '选择OCR引擎...'}
        )
        
        engine = ocr_service._select_engine(engine_preference)
        task.engine_used = engine
        db.commit()
        
        logger.info(f"任务 {task.id} 使用引擎: {engine}, 总页数: {len(images)}")
        
        # 处理每个图像
        celery_task.update_state(
            state='PROGRESS',
            meta={'current': 3, 'total': 4, 'status': f'处理 {len(images)} 页图像...'}
        )
        
        all_results = []
        successful_pages = 0
        
        for i, image in enumerate(images):
            try:
                # 更新进度
                celery_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': 3,
                        'total': 4,
                        'status': f'处理第 {i+1}/{len(images)} 页...',
                        'page_progress': i + 1,
                        'total_pages': len(images)
                    }
                )
                
                # 执行OCR
                result = await ocr_service._execute_ocr(engine, image)
                
                # 保存结果
                ocr_result = OCRResult(
                    task_id=task.id,
                    page_number=i + 1,
                    text_content=result['text'],
                    confidence_score=result['confidence'],
                    bounding_boxes=result['blocks'],
                    engine_used=engine
                )
                
                db.add(ocr_result)
                all_results.append(result)
                successful_pages += 1
                
                # 更新进度
                task.processed_pages = successful_pages
                db.commit()
                
                logger.debug(f"页面 {i+1} 处理完成, 置信度: {result['confidence']:.2f}")
                
            except Exception as e:
                logger.error(f"处理第{i+1}页失败: {e}")
                # 创建失败记录
                ocr_result = OCRResult(
                    task_id=task.id,
                    page_number=i + 1,
                    text_content="",
                    confidence_score=0.0,
                    bounding_boxes=[],
                    engine_used=engine,
                    error_message=str(e)
                )
                db.add(ocr_result)
                db.commit()
                continue
        
        # 完成处理
        celery_task.update_state(
            state='PROGRESS',
            meta={'current': 4, 'total': 4, 'status': '完成处理...'}
        )
        
        # 更新任务状态
        task.status = "completed"
        task.completed_at = datetime.now()
        
        # 计算总体置信度
        if all_results:
            avg_confidence = sum(r['confidence'] for r in all_results) / len(all_results)
            task.confidence_score = avg_confidence
        else:
            task.confidence_score = 0.0
        
        db.commit()
        
        # 记录API使用
        ocr_service._record_api_usage(db, task.user_id, engine, len(images))
        
        # 更新文件状态
        file_record.status = "completed"
        file_record.processed_at = datetime.now()
        db.commit()
        
        logger.info(f"任务 {task.id} 处理完成: {successful_pages}/{len(images)} 页成功")
        
        return {
            "success": True,
            "pages_processed": successful_pages,
            "total_pages": len(images),
            "avg_confidence": task.confidence_score
        }
        
    except Exception as e:
        logger.error(f"OCR处理失败: {e}")
        raise


@celery_app.task
def batch_process_ocr_tasks(task_ids: list, engine_preference: str = None):
    """批量处理OCR任务"""
    logger.info(f"开始批量处理 {len(task_ids)} 个OCR任务")
    
    results = []
    for task_id in task_ids:
        try:
            result = process_ocr_task.delay(task_id, engine_preference)
            results.append({
                "task_id": task_id,
                "celery_task_id": result.id,
                "status": "submitted"
            })
        except Exception as e:
            logger.error(f"提交任务失败: {task_id} - {e}")
            results.append({
                "task_id": task_id,
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "total_tasks": len(task_ids),
        "submitted_tasks": len([r for r in results if r["status"] == "submitted"]),
        "failed_tasks": len([r for r in results if r["status"] == "failed"]),
        "results": results
    }


@celery_app.task
def get_task_progress(task_id: int):
    """获取任务进度"""
    with get_db_session() as db:
        task = db.query(OCRTask).filter(OCRTask.id == task_id).first()
        if not task:
            return {"error": "任务不存在"}
        
        progress = {
            "task_id": task_id,
            "status": task.status,
            "total_pages": task.total_pages,
            "processed_pages": task.processed_pages,
            "engine_used": task.engine_used,
            "confidence_score": task.confidence_score,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message
        }
        
        # 计算进度百分比
        if task.total_pages > 0:
            progress["progress_percent"] = (task.processed_pages / task.total_pages) * 100
        else:
            progress["progress_percent"] = 0
        
        return progress


@celery_app.task
def cancel_ocr_task(task_id: int):
    """取消OCR任务"""
    with get_db_session() as db:
        task = db.query(OCRTask).filter(OCRTask.id == task_id).first()
        if not task:
            return {"error": "任务不存在"}
        
        if task.status in ["completed", "failed", "cancelled"]:
            return {"error": "任务已完成或已取消"}
        
        # 取消Celery任务
        if task.celery_task_id:
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        
        # 更新任务状态
        task.status = "cancelled"
        task.completed_at = datetime.now()
        db.commit()
        
        logger.info(f"任务已取消: {task_id}")
        
        return {"status": "cancelled", "task_id": task_id}