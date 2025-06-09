from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from database import get_db
from models import User, UserQuota, APIUsage, OCRTask, File as FileModel
from services.auth_service import AuthService
from utils.security import get_current_user, check_admin_permission
from utils.logger import log_user_activity, log_security_event
from config import settings

router = APIRouter(prefix="/users", tags=["用户管理"])
auth_service = AuthService()


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    plan: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserQuotaResponse(BaseModel):
    daily_limit: int
    monthly_limit: int
    daily_used: int
    monthly_used: int
    daily_remaining: int
    monthly_remaining: int
    reset_daily_at: datetime
    reset_monthly_at: datetime
    
    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    
    class Config:
        schema_extra = {
            "example": {
                "full_name": "张三",
                "email": "zhangsan@example.com"
            }
        }


class UserStatsResponse(BaseModel):
    total_files: int
    total_ocr_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_storage_mb: float
    total_api_calls: int
    account_age_days: int
    favorite_engine: str
    most_used_language: str
    

class APIUsageResponse(BaseModel):
    date: str
    api_calls: int
    ocr_tasks: int
    files_uploaded: int
    storage_used_mb: float
    

class UserActivityResponse(BaseModel):
    id: int
    activity_type: str
    description: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    details: Optional[Dict[str, Any]]
    
    class Config:
        from_attributes = True


@router.get("/profile", response_model=UserProfileResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """获取用户资料"""
    return current_user


@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    profile_data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户资料"""
    try:
        # 检查邮箱是否已被使用
        if profile_data.email and profile_data.email != current_user.email:
            existing_user = auth_service.get_user_by_email(db, profile_data.email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被使用"
                )
        
        # 更新用户信息
        update_data = {}
        if profile_data.full_name is not None:
            update_data["full_name"] = profile_data.full_name
        if profile_data.email is not None:
            update_data["email"] = profile_data.email
        
        if update_data:
            for key, value in update_data.items():
                setattr(current_user, key, value)
            
            db.commit()
            db.refresh(current_user)
            
            # 记录用户活动
            log_user_activity(
                user_id=current_user.id,
                activity="profile_updated",
                details=update_data
            )
        
        return current_user
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户资料失败"
        )


@router.get("/quota", response_model=UserQuotaResponse)
async def get_user_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户配额信息"""
    try:
        quota = db.query(UserQuota).filter(UserQuota.user_id == current_user.id).first()
        
        if not quota:
            # 创建默认配额
            quota = auth_service.create_user_quota(db, current_user.id, current_user.plan)
        
        # 计算剩余配额
        daily_remaining = max(0, quota.daily_limit - quota.daily_used)
        monthly_remaining = max(0, quota.monthly_limit - quota.monthly_used)
        
        return UserQuotaResponse(
            daily_limit=quota.daily_limit,
            monthly_limit=quota.monthly_limit,
            daily_used=quota.daily_used,
            monthly_used=quota.monthly_used,
            daily_remaining=daily_remaining,
            monthly_remaining=monthly_remaining,
            reset_daily_at=quota.reset_daily_at,
            reset_monthly_at=quota.reset_monthly_at
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取配额信息失败"
        )


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户统计信息"""
    try:
        # 文件统计
        files_query = db.query(FileModel).filter(FileModel.user_id == current_user.id)
        total_files = files_query.count()
        total_storage = sum(f.file_size for f in files_query.all())
        
        # OCR任务统计
        tasks_query = db.query(OCRTask).filter(OCRTask.user_id == current_user.id)
        total_ocr_tasks = tasks_query.count()
        completed_tasks = tasks_query.filter(OCRTask.status == "completed").count()
        failed_tasks = tasks_query.filter(OCRTask.status == "failed").count()
        
        # API使用统计
        api_usage_query = db.query(APIUsage).filter(APIUsage.user_id == current_user.id)
        total_api_calls = api_usage_query.count()
        
        # 账户年龄
        account_age = (datetime.now() - current_user.created_at).days
        
        # 最常用引擎
        engine_stats = {}
        for task in tasks_query.all():
            engine = task.engine
            engine_stats[engine] = engine_stats.get(engine, 0) + 1
        
        favorite_engine = max(engine_stats.items(), key=lambda x: x[1])[0] if engine_stats else "无"
        
        # 最常用语言
        language_stats = {}
        for task in tasks_query.all():
            language = task.language
            language_stats[language] = language_stats.get(language, 0) + 1
        
        most_used_language = max(language_stats.items(), key=lambda x: x[1])[0] if language_stats else "无"
        
        return UserStatsResponse(
            total_files=total_files,
            total_ocr_tasks=total_ocr_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            total_storage_mb=round(total_storage / 1024 / 1024, 2),
            total_api_calls=total_api_calls,
            account_age_days=account_age,
            favorite_engine=favorite_engine,
            most_used_language=most_used_language
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取统计信息失败"
        )


@router.get("/usage", response_model=List[APIUsageResponse])
async def get_usage_history(
    days: int = Query(30, ge=1, le=365, description="查询天数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户使用历史"""
    try:
        from sqlalchemy import func, and_
        
        start_date = datetime.now() - timedelta(days=days)
        
        # 按日期聚合API使用情况
        api_usage = db.query(
            func.date(APIUsage.created_at).label('date'),
            func.count(APIUsage.id).label('api_calls')
        ).filter(
            and_(
                APIUsage.user_id == current_user.id,
                APIUsage.created_at >= start_date
            )
        ).group_by(func.date(APIUsage.created_at)).all()
        
        # 按日期聚合OCR任务
        ocr_tasks = db.query(
            func.date(OCRTask.created_at).label('date'),
            func.count(OCRTask.id).label('ocr_tasks')
        ).filter(
            and_(
                OCRTask.user_id == current_user.id,
                OCRTask.created_at >= start_date
            )
        ).group_by(func.date(OCRTask.created_at)).all()
        
        # 按日期聚合文件上传
        files_uploaded = db.query(
            func.date(FileModel.upload_time).label('date'),
            func.count(FileModel.id).label('files_uploaded'),
            func.sum(FileModel.file_size).label('storage_used')
        ).filter(
            and_(
                FileModel.user_id == current_user.id,
                FileModel.upload_time >= start_date
            )
        ).group_by(func.date(FileModel.upload_time)).all()
        
        # 合并数据
        usage_data = {}
        
        for usage in api_usage:
            date_str = usage.date.strftime('%Y-%m-%d')
            usage_data[date_str] = usage_data.get(date_str, {
                'date': date_str,
                'api_calls': 0,
                'ocr_tasks': 0,
                'files_uploaded': 0,
                'storage_used_mb': 0.0
            })
            usage_data[date_str]['api_calls'] = usage.api_calls
        
        for task in ocr_tasks:
            date_str = task.date.strftime('%Y-%m-%d')
            usage_data[date_str] = usage_data.get(date_str, {
                'date': date_str,
                'api_calls': 0,
                'ocr_tasks': 0,
                'files_uploaded': 0,
                'storage_used_mb': 0.0
            })
            usage_data[date_str]['ocr_tasks'] = task.ocr_tasks
        
        for file_data in files_uploaded:
            date_str = file_data.date.strftime('%Y-%m-%d')
            usage_data[date_str] = usage_data.get(date_str, {
                'date': date_str,
                'api_calls': 0,
                'ocr_tasks': 0,
                'files_uploaded': 0,
                'storage_used_mb': 0.0
            })
            usage_data[date_str]['files_uploaded'] = file_data.files_uploaded
            usage_data[date_str]['storage_used_mb'] = round(
                (file_data.storage_used or 0) / 1024 / 1024, 2
            )
        
        # 转换为列表并排序
        result = [APIUsageResponse(**data) for data in usage_data.values()]
        result.sort(key=lambda x: x.date, reverse=True)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取使用历史失败"
        )


@router.post("/upgrade-plan")
async def upgrade_user_plan(
    new_plan: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """升级用户计划"""
    valid_plans = ["free", "basic", "premium", "enterprise"]
    
    if new_plan not in valid_plans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的计划类型，支持的计划: {', '.join(valid_plans)}"
        )
    
    # 检查是否为降级（简单检查）
    plan_levels = {"free": 0, "basic": 1, "premium": 2, "enterprise": 3}
    current_level = plan_levels.get(current_user.plan, 0)
    new_level = plan_levels.get(new_plan, 0)
    
    if new_level < current_level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持降级操作，请联系客服"
        )
    
    if current_user.plan == new_plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户已经是该计划"
        )
    
    try:
        # 更新用户计划
        old_plan = current_user.plan
        auth_service.update_user_plan(db, current_user.id, new_plan)
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="plan_upgraded",
            details={
                "old_plan": old_plan,
                "new_plan": new_plan
            }
        )
        
        # 记录安全事件
        log_security_event(
            event_type="plan_change",
            user_id=current_user.id,
            details={
                "old_plan": old_plan,
                "new_plan": new_plan,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "message": f"计划已升级为 {new_plan}",
            "old_plan": old_plan,
            "new_plan": new_plan
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="计划升级失败"
        )


@router.post("/deactivate")
async def deactivate_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """停用账户"""
    try:
        # 停用用户账户
        auth_service.deactivate_user(db, current_user.id)
        
        # 记录安全事件
        log_security_event(
            event_type="account_deactivated",
            user_id=current_user.id,
            details={
                "deactivated_at": datetime.now().isoformat(),
                "self_deactivated": True
            }
        )
        
        return {"message": "账户已停用"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="账户停用失败"
        )


@router.get("/preferences")
async def get_user_preferences(
    current_user: User = Depends(get_current_user)
):
    """获取用户偏好设置"""
    # 从用户的历史使用中推断偏好
    # 这里可以扩展为存储在数据库中的用户偏好
    return {
        "default_language": "chi_sim+eng",
        "default_engine": "auto",
        "auto_preprocess": True,
        "notification_enabled": True,
        "theme": "light",
        "timezone": "Asia/Shanghai"
    }


@router.put("/preferences")
async def update_user_preferences(
    preferences: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户偏好设置"""
    try:
        # 这里可以扩展为将偏好设置存储到数据库
        # 目前只是记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="preferences_updated",
            details=preferences
        )
        
        return {
            "message": "偏好设置已更新",
            "preferences": preferences
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新偏好设置失败"
        )


@router.get("/export-data")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """导出用户数据"""
    try:
        # 获取用户的所有数据
        user_data = {
            "user_info": {
                "id": current_user.id,
                "username": current_user.username,
                "email": current_user.email,
                "full_name": current_user.full_name,
                "plan": current_user.plan,
                "created_at": current_user.created_at.isoformat(),
                "last_login": current_user.last_login.isoformat() if current_user.last_login else None
            },
            "files": [],
            "ocr_tasks": [],
            "api_usage": []
        }
        
        # 文件数据
        files = db.query(FileModel).filter(FileModel.user_id == current_user.id).all()
        for file_record in files:
            user_data["files"].append({
                "id": file_record.id,
                "filename": file_record.original_filename,
                "file_size": file_record.file_size,
                "file_type": file_record.file_type,
                "upload_time": file_record.upload_time.isoformat(),
                "status": file_record.status
            })
        
        # OCR任务数据
        tasks = db.query(OCRTask).filter(OCRTask.user_id == current_user.id).all()
        for task in tasks:
            user_data["ocr_tasks"].append({
                "id": task.id,
                "task_id": task.task_id,
                "engine": task.engine,
                "language": task.language,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "completed_at": task.completed_at.isoformat() if task.completed_at else None
            })
        
        # API使用数据
        api_usage = db.query(APIUsage).filter(APIUsage.user_id == current_user.id).all()
        for usage in api_usage:
            user_data["api_usage"].append({
                "id": usage.id,
                "endpoint": usage.endpoint,
                "method": usage.method,
                "status_code": usage.status_code,
                "created_at": usage.created_at.isoformat()
            })
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="data_exported",
            details={"export_time": datetime.now().isoformat()}
        )
        
        return user_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="数据导出失败"
        )