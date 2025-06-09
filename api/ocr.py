from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from celery.result import AsyncResult

from database import get_db
from models import User, OCRTask, OCRResult
from services.ocr_service import OCRService
from services.file_service import FileService
from utils.security import get_current_user
from utils.logger import log_user_activity, log_performance
from tasks.ocr_tasks import process_ocr_task, batch_process_ocr_tasks, cancel_ocr_task
from config import settings

router = APIRouter(prefix="/ocr", tags=["OCR识别"])
ocr_service = OCRService()
file_service = FileService()


class OCRRequest(BaseModel):
    engine: Optional[str] = None
    language: str = "auto"
    preprocess: bool = True
    extract_tables: bool = False
    extract_layout: bool = False
    confidence_threshold: float = 0.5
    
    class Config:
        schema_extra = {
            "example": {
                "engine": "tesseract",
                "language": "chi_sim+eng",
                "preprocess": True,
                "extract_tables": False,
                "extract_layout": False,
                "confidence_threshold": 0.5
            }
        }


class BatchOCRRequest(BaseModel):
    file_ids: List[int]
    engine: Optional[str] = None
    language: str = "auto"
    preprocess: bool = True
    extract_tables: bool = False
    extract_layout: bool = False
    confidence_threshold: float = 0.5
    priority: int = 1  # 1-5, 5为最高优先级


class OCRTaskResponse(BaseModel):
    task_id: str
    file_id: int
    status: str
    engine: str
    language: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress: int
    error_message: Optional[str]
    
    class Config:
        from_attributes = True


class OCRResultResponse(BaseModel):
    id: int
    task_id: str
    text: str
    confidence: float
    processing_time: float
    word_count: int
    character_count: int
    bounding_boxes: Optional[Dict[str, Any]]
    tables: Optional[List[Dict[str, Any]]]
    layout_info: Optional[Dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class OCREngineInfo(BaseModel):
    name: str
    display_name: str
    type: str  # free or paid
    languages: List[str]
    features: List[str]
    cost_per_page: float
    accuracy_rating: float
    speed_rating: float
    available: bool
    description: str


class OCRStatsResponse(BaseModel):
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    total_pages_processed: int
    total_processing_time: float
    average_confidence: float
    engine_usage: Dict[str, int]
    language_usage: Dict[str, int]


@router.post("/process", response_model=OCRTaskResponse)
async def process_file_ocr(
    file_id: int,
    ocr_request: OCRRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """处理单个文件的OCR识别"""
    try:
        # 检查文件是否存在
        file_record = file_service.get_file_by_id(db, file_id, current_user.id)
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        
        # 检查文件状态
        if file_record.status != "uploaded":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件状态不允许进行OCR处理"
            )
        
        # 检查用户配额
        if not ocr_service.check_user_quota(db, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="已超出使用配额限制"
            )
        
        # 选择OCR引擎
        selected_engine = ocr_service.select_ocr_engine(
            db=db,
            user_id=current_user.id,
            preferred_engine=ocr_request.engine,
            file_type=file_record.file_type
        )
        
        # 创建OCR任务
        task_data = {
            "file_id": file_id,
            "user_id": current_user.id,
            "engine": selected_engine,
            "language": ocr_request.language,
            "preprocess": ocr_request.preprocess,
            "extract_tables": ocr_request.extract_tables,
            "extract_layout": ocr_request.extract_layout,
            "confidence_threshold": ocr_request.confidence_threshold
        }
        
        # 提交异步任务
        celery_task = process_ocr_task.delay(**task_data)
        
        # 创建数据库记录
        ocr_task = OCRTask(
            task_id=celery_task.id,
            file_id=file_id,
            user_id=current_user.id,
            engine=selected_engine,
            language=ocr_request.language,
            status="pending",
            parameters={
                "preprocess": ocr_request.preprocess,
                "extract_tables": ocr_request.extract_tables,
                "extract_layout": ocr_request.extract_layout,
                "confidence_threshold": ocr_request.confidence_threshold
            }
        )
        
        db.add(ocr_task)
        db.commit()
        db.refresh(ocr_task)
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="ocr_task_created",
            details={
                "task_id": celery_task.id,
                "file_id": file_id,
                "engine": selected_engine,
                "language": ocr_request.language
            }
        )
        
        return ocr_task
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OCR任务创建失败"
        )


@router.post("/process/batch", response_model=List[OCRTaskResponse])
async def process_batch_ocr(
    batch_request: BatchOCRRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量处理OCR识别"""
    if len(batch_request.file_ids) > settings.max_batch_ocr:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"一次最多只能处理 {settings.max_batch_ocr} 个文件"
        )
    
    try:
        # 验证所有文件
        valid_files = []
        for file_id in batch_request.file_ids:
            file_record = file_service.get_file_by_id(db, file_id, current_user.id)
            if file_record and file_record.status == "uploaded":
                valid_files.append(file_id)
        
        if not valid_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有可处理的有效文件"
            )
        
        # 检查用户配额
        if not ocr_service.check_user_quota(db, current_user.id, len(valid_files)):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="批量处理超出配额限制"
            )
        
        # 创建批量任务
        task_data = {
            "file_ids": valid_files,
            "user_id": current_user.id,
            "engine": batch_request.engine,
            "language": batch_request.language,
            "preprocess": batch_request.preprocess,
            "extract_tables": batch_request.extract_tables,
            "extract_layout": batch_request.extract_layout,
            "confidence_threshold": batch_request.confidence_threshold,
            "priority": batch_request.priority
        }
        
        # 提交批量任务
        celery_task = batch_process_ocr_tasks.delay(**task_data)
        
        # 创建任务记录
        created_tasks = []
        for file_id in valid_files:
            ocr_task = OCRTask(
                task_id=f"{celery_task.id}_{file_id}",
                file_id=file_id,
                user_id=current_user.id,
                engine=batch_request.engine or "auto",
                language=batch_request.language,
                status="pending",
                parameters={
                    "batch_id": celery_task.id,
                    "preprocess": batch_request.preprocess,
                    "extract_tables": batch_request.extract_tables,
                    "extract_layout": batch_request.extract_layout,
                    "confidence_threshold": batch_request.confidence_threshold,
                    "priority": batch_request.priority
                }
            )
            
            db.add(ocr_task)
            created_tasks.append(ocr_task)
        
        db.commit()
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="batch_ocr_created",
            details={
                "batch_id": celery_task.id,
                "file_count": len(valid_files),
                "engine": batch_request.engine,
                "priority": batch_request.priority
            }
        )
        
        return created_tasks
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量OCR任务创建失败"
        )


@router.post("/upload-and-process", response_model=OCRTaskResponse)
async def upload_and_process(
    file: UploadFile = File(...),
    engine: Optional[str] = None,
    language: str = "auto",
    preprocess: bool = True,
    extract_tables: bool = False,
    extract_layout: bool = False,
    confidence_threshold: float = 0.5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传文件并立即处理OCR"""
    try:
        # 上传文件
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要上传的文件"
            )
        
        file_content = await file.read()
        
        if len(file_content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容为空"
            )
        
        # 保存文件
        file_record = await file_service.save_uploaded_file(
            db=db,
            user_id=current_user.id,
            original_filename=file.filename,
            file_content=file_content
        )
        
        # 创建OCR请求
        ocr_request = OCRRequest(
            engine=engine,
            language=language,
            preprocess=preprocess,
            extract_tables=extract_tables,
            extract_layout=extract_layout,
            confidence_threshold=confidence_threshold
        )
        
        # 处理OCR
        return await process_file_ocr(
            file_id=file_record.id,
            ocr_request=ocr_request,
            background_tasks=BackgroundTasks(),
            current_user=current_user,
            db=db
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件上传和OCR处理失败"
        )


@router.get("/tasks/{task_id}", response_model=OCRTaskResponse)
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取OCR任务状态"""
    task = db.query(OCRTask).filter(
        OCRTask.task_id == task_id,
        OCRTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 获取Celery任务状态
    celery_task = AsyncResult(task_id)
    
    # 更新任务状态
    if celery_task.state == "PENDING":
        task.status = "pending"
    elif celery_task.state == "STARTED":
        task.status = "processing"
        if not task.started_at:
            task.started_at = datetime.now()
    elif celery_task.state == "SUCCESS":
        task.status = "completed"
        if not task.completed_at:
            task.completed_at = datetime.now()
    elif celery_task.state == "FAILURE":
        task.status = "failed"
        task.error_message = str(celery_task.info)
        if not task.completed_at:
            task.completed_at = datetime.now()
    
    # 获取进度信息
    if hasattr(celery_task.info, 'get') and celery_task.info.get('progress'):
        task.progress = celery_task.info['progress']
    
    db.commit()
    
    return task


@router.get("/tasks", response_model=List[OCRTaskResponse])
async def get_user_tasks(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    engine: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户的OCR任务列表"""
    query = db.query(OCRTask).filter(OCRTask.user_id == current_user.id)
    
    if status:
        query = query.filter(OCRTask.status == status)
    
    if engine:
        query = query.filter(OCRTask.engine == engine)
    
    # 分页
    offset = (page - 1) * size
    tasks = query.order_by(OCRTask.created_at.desc()).offset(offset).limit(size).all()
    
    return tasks


@router.get("/results/{task_id}", response_model=OCRResultResponse)
async def get_ocr_result(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取OCR识别结果"""
    # 验证任务所有权
    task = db.query(OCRTask).filter(
        OCRTask.task_id == task_id,
        OCRTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    # 获取结果
    result = db.query(OCRResult).filter(OCRResult.task_id == task_id).first()
    
    if not result:
        if task.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="OCR结果不存在"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"任务尚未完成，当前状态: {task.status}"
            )
    
    return result


@router.delete("/tasks/{task_id}")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """取消OCR任务"""
    task = db.query(OCRTask).filter(
        OCRTask.task_id == task_id,
        OCRTask.user_id == current_user.id
    ).first()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    if task.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="任务已完成或已取消，无法取消"
        )
    
    try:
        # 取消Celery任务
        cancel_ocr_task.delay(task_id)
        
        # 更新任务状态
        task.status = "cancelled"
        task.completed_at = datetime.now()
        db.commit()
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="task_cancelled",
            details={"task_id": task_id}
        )
        
        return {"message": "任务已取消"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务取消失败"
        )


@router.get("/engines", response_model=List[OCREngineInfo])
async def get_available_engines(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取可用的OCR引擎列表"""
    try:
        engines = ocr_service.get_available_engines(db, current_user.id)
        return engines
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取引擎列表失败"
        )


@router.get("/stats", response_model=OCRStatsResponse)
async def get_ocr_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取OCR使用统计"""
    try:
        from datetime import datetime, timedelta
        
        start_date = datetime.now() - timedelta(days=days)
        
        # 基础统计
        tasks_query = db.query(OCRTask).filter(
            OCRTask.user_id == current_user.id,
            OCRTask.created_at >= start_date
        )
        
        total_tasks = tasks_query.count()
        completed_tasks = tasks_query.filter(OCRTask.status == "completed").count()
        failed_tasks = tasks_query.filter(OCRTask.status == "failed").count()
        pending_tasks = tasks_query.filter(OCRTask.status.in_(["pending", "processing"])).count()
        
        # 引擎使用统计
        engine_stats = {}
        for task in tasks_query.all():
            engine = task.engine
            engine_stats[engine] = engine_stats.get(engine, 0) + 1
        
        # 语言使用统计
        language_stats = {}
        for task in tasks_query.all():
            language = task.language
            language_stats[language] = language_stats.get(language, 0) + 1
        
        # 结果统计
        results_query = db.query(OCRResult).join(OCRTask).filter(
            OCRTask.user_id == current_user.id,
            OCRTask.created_at >= start_date
        )
        
        total_pages = sum(result.page_count or 1 for result in results_query.all())
        total_time = sum(result.processing_time for result in results_query.all())
        avg_confidence = db.query(db.func.avg(OCRResult.confidence)).join(OCRTask).filter(
            OCRTask.user_id == current_user.id,
            OCRTask.created_at >= start_date
        ).scalar() or 0.0
        
        return OCRStatsResponse(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            pending_tasks=pending_tasks,
            total_pages_processed=total_pages,
            total_processing_time=total_time,
            average_confidence=round(avg_confidence, 2),
            engine_usage=engine_stats,
            language_usage=language_stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败"
        )


@router.get("/languages")
async def get_supported_languages():
    """获取支持的语言列表"""
    return {
        "languages": {
            "auto": "自动检测",
            "chi_sim": "简体中文",
            "chi_tra": "繁体中文",
            "eng": "英语",
            "jpn": "日语",
            "kor": "韩语",
            "fra": "法语",
            "deu": "德语",
            "spa": "西班牙语",
            "rus": "俄语",
            "ara": "阿拉伯语",
            "tha": "泰语",
            "vie": "越南语"
        },
        "combinations": {
            "chi_sim+eng": "中英混合",
            "chi_tra+eng": "繁体中文+英语",
            "jpn+eng": "日英混合",
            "kor+eng": "韩英混合"
        }
    }


@router.post("/test-engine")
async def test_ocr_engine(
    engine: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """测试OCR引擎可用性"""
    try:
        # 检查引擎是否可用
        available_engines = ocr_service.get_available_engines(db, current_user.id)
        engine_info = next((e for e in available_engines if e.name == engine), None)
        
        if not engine_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="引擎不存在或不可用"
            )
        
        # 执行引擎测试
        test_result = await ocr_service.test_engine(engine)
        
        return {
            "engine": engine,
            "available": test_result["success"],
            "response_time": test_result.get("response_time", 0),
            "error": test_result.get("error"),
            "test_time": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="引擎测试失败"
        )