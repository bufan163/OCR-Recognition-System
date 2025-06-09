from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from database import get_db
from models import User, UserQuota, APIUsage, OCRTask, OCRResult, File as FileModel, SystemConfig, OCREngine
from services.auth_service import AuthService
from utils.security import get_current_user, check_admin_permission
from utils.logger import log_user_activity, log_security_event, log_system_event
from config import settings

router = APIRouter(prefix="/admin", tags=["管理员"])
auth_service = AuthService()


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    plan: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    total_files: int
    total_tasks: int
    storage_used_mb: float
    
    class Config:
        from_attributes = True


class SystemStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_files: int
    total_storage_gb: float
    total_ocr_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    daily_api_calls: int
    monthly_api_calls: int
    engine_usage: Dict[str, int]
    plan_distribution: Dict[str, int]
    

class UserManagementRequest(BaseModel):
    plan: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    daily_limit: Optional[int] = None
    monthly_limit: Optional[int] = None


class SystemConfigResponse(BaseModel):
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UpdateSystemConfigRequest(BaseModel):
    value: str
    description: Optional[str] = None


class OCREngineResponse(BaseModel):
    id: int
    name: str
    display_name: str
    engine_type: str
    is_enabled: bool
    priority: int
    cost_per_page: float
    max_requests_per_minute: int
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UpdateOCREngineRequest(BaseModel):
    display_name: Optional[str] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None
    cost_per_page: Optional[float] = None
    max_requests_per_minute: Optional[int] = None
    config: Optional[Dict[str, Any]] = None


# 依赖项：检查管理员权限
def get_admin_user(current_user: User = Depends(get_current_user)):
    if not check_admin_permission(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )
    return current_user


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """获取系统统计信息"""
    try:
        # 用户统计
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        
        # 文件统计
        total_files = db.query(FileModel).count()
        total_storage = db.query(func.sum(FileModel.file_size)).scalar() or 0
        
        # OCR任务统计
        total_ocr_tasks = db.query(OCRTask).count()
        completed_tasks = db.query(OCRTask).filter(OCRTask.status == "completed").count()
        failed_tasks = db.query(OCRTask).filter(OCRTask.status == "failed").count()
        pending_tasks = db.query(OCRTask).filter(
            OCRTask.status.in_(["pending", "processing"])
        ).count()
        
        # API调用统计
        today = datetime.now().date()
        daily_api_calls = db.query(APIUsage).filter(
            func.date(APIUsage.created_at) == today
        ).count()
        
        this_month = datetime.now().replace(day=1).date()
        monthly_api_calls = db.query(APIUsage).filter(
            APIUsage.created_at >= this_month
        ).count()
        
        # 引擎使用统计
        engine_usage = {}
        engine_stats = db.query(
            OCRTask.engine,
            func.count(OCRTask.id)
        ).group_by(OCRTask.engine).all()
        
        for engine, count in engine_stats:
            engine_usage[engine] = count
        
        # 计划分布
        plan_distribution = {}
        plan_stats = db.query(
            User.plan,
            func.count(User.id)
        ).group_by(User.plan).all()
        
        for plan, count in plan_stats:
            plan_distribution[plan] = count
        
        return SystemStatsResponse(
            total_users=total_users,
            active_users=active_users,
            total_files=total_files,
            total_storage_gb=round(total_storage / 1024 / 1024 / 1024, 2),
            total_ocr_tasks=total_ocr_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            pending_tasks=pending_tasks,
            daily_api_calls=daily_api_calls,
            monthly_api_calls=monthly_api_calls,
            engine_usage=engine_usage,
            plan_distribution=plan_distribution
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统统计失败"
        )


@router.get("/users", response_model=List[AdminUserResponse])
async def get_all_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索用户名或邮箱"),
    plan: Optional[str] = Query(None, description="按计划筛选"),
    is_active: Optional[bool] = Query(None, description="按状态筛选"),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """获取所有用户列表"""
    try:
        query = db.query(User)
        
        # 搜索过滤
        if search:
            query = query.filter(
                or_(
                    User.username.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                    User.full_name.ilike(f"%{search}%")
                )
            )
        
        # 计划过滤
        if plan:
            query = query.filter(User.plan == plan)
        
        # 状态过滤
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # 分页
        offset = (page - 1) * size
        users = query.order_by(User.created_at.desc()).offset(offset).limit(size).all()
        
        # 为每个用户添加统计信息
        result = []
        for user in users:
            # 文件统计
            user_files = db.query(FileModel).filter(FileModel.user_id == user.id)
            total_files = user_files.count()
            storage_used = sum(f.file_size for f in user_files.all())
            
            # 任务统计
            total_tasks = db.query(OCRTask).filter(OCRTask.user_id == user.id).count()
            
            user_data = AdminUserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                plan=user.plan,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at,
                last_login=user.last_login,
                total_files=total_files,
                total_tasks=total_tasks,
                storage_used_mb=round(storage_used / 1024 / 1024, 2)
            )
            result.append(user_data)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取用户列表失败"
        )


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user_details(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """获取用户详细信息"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 添加统计信息
    user_files = db.query(FileModel).filter(FileModel.user_id == user.id)
    total_files = user_files.count()
    storage_used = sum(f.file_size for f in user_files.all())
    total_tasks = db.query(OCRTask).filter(OCRTask.user_id == user.id).count()
    
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        plan=user.plan,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        last_login=user.last_login,
        total_files=total_files,
        total_tasks=total_tasks,
        storage_used_mb=round(storage_used / 1024 / 1024, 2)
    )


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    update_data: UserManagementRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """更新用户信息"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    try:
        changes = {}
        
        # 更新用户基本信息
        if update_data.plan is not None:
            old_plan = user.plan
            user.plan = update_data.plan
            changes["plan"] = {"old": old_plan, "new": update_data.plan}
            
            # 更新用户配额
            auth_service.update_user_plan(db, user_id, update_data.plan)
        
        if update_data.is_active is not None:
            old_status = user.is_active
            user.is_active = update_data.is_active
            changes["is_active"] = {"old": old_status, "new": update_data.is_active}
        
        if update_data.is_admin is not None:
            old_admin = user.is_admin
            user.is_admin = update_data.is_admin
            changes["is_admin"] = {"old": old_admin, "new": update_data.is_admin}
        
        # 更新配额
        if update_data.daily_limit is not None or update_data.monthly_limit is not None:
            quota = db.query(UserQuota).filter(UserQuota.user_id == user_id).first()
            if quota:
                if update_data.daily_limit is not None:
                    old_daily = quota.daily_limit
                    quota.daily_limit = update_data.daily_limit
                    changes["daily_limit"] = {"old": old_daily, "new": update_data.daily_limit}
                
                if update_data.monthly_limit is not None:
                    old_monthly = quota.monthly_limit
                    quota.monthly_limit = update_data.monthly_limit
                    changes["monthly_limit"] = {"old": old_monthly, "new": update_data.monthly_limit}
        
        db.commit()
        
        # 记录管理员操作
        log_user_activity(
            user_id=admin_user.id,
            activity="admin_user_updated",
            details={
                "target_user_id": user_id,
                "changes": changes
            }
        )
        
        # 记录安全事件
        log_security_event(
            event_type="user_modified_by_admin",
            user_id=user_id,
            details={
                "admin_id": admin_user.id,
                "changes": changes,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "message": "用户信息已更新",
            "changes": changes
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新用户信息失败"
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """删除用户（软删除）"""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除管理员用户"
        )
    
    try:
        # 软删除：停用用户
        user.is_active = False
        
        # 取消所有进行中的任务
        pending_tasks = db.query(OCRTask).filter(
            OCRTask.user_id == user_id,
            OCRTask.status.in_(["pending", "processing"])
        ).all()
        
        for task in pending_tasks:
            task.status = "cancelled"
            task.completed_at = datetime.now()
        
        db.commit()
        
        # 记录管理员操作
        log_user_activity(
            user_id=admin_user.id,
            activity="admin_user_deleted",
            details={
                "target_user_id": user_id,
                "username": user.username,
                "cancelled_tasks": len(pending_tasks)
            }
        )
        
        # 记录安全事件
        log_security_event(
            event_type="user_deleted_by_admin",
            user_id=user_id,
            details={
                "admin_id": admin_user.id,
                "username": user.username,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "message": "用户已删除",
            "cancelled_tasks": len(pending_tasks)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除用户失败"
        )


@router.get("/config", response_model=List[SystemConfigResponse])
async def get_system_config(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """获取系统配置"""
    try:
        configs = db.query(SystemConfig).order_by(SystemConfig.key).all()
        return configs
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取系统配置失败"
        )


@router.put("/config/{config_key}")
async def update_system_config(
    config_key: str,
    update_data: UpdateSystemConfigRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """更新系统配置"""
    try:
        config = db.query(SystemConfig).filter(SystemConfig.key == config_key).first()
        
        if not config:
            # 创建新配置
            config = SystemConfig(
                key=config_key,
                value=update_data.value,
                description=update_data.description
            )
            db.add(config)
        else:
            # 更新现有配置
            old_value = config.value
            config.value = update_data.value
            if update_data.description is not None:
                config.description = update_data.description
            config.updated_at = datetime.now()
        
        db.commit()
        
        # 记录系统事件
        log_system_event(
            event_type="config_updated",
            details={
                "key": config_key,
                "old_value": old_value if config else None,
                "new_value": update_data.value,
                "admin_id": admin_user.id
            }
        )
        
        return {
            "message": "系统配置已更新",
            "key": config_key,
            "value": update_data.value
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新系统配置失败"
        )


@router.get("/engines", response_model=List[OCREngineResponse])
async def get_ocr_engines(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """获取OCR引擎配置"""
    try:
        engines = db.query(OCREngine).order_by(OCREngine.priority.desc()).all()
        return engines
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取OCR引擎配置失败"
        )


@router.put("/engines/{engine_id}")
async def update_ocr_engine(
    engine_id: int,
    update_data: UpdateOCREngineRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """更新OCR引擎配置"""
    engine = db.query(OCREngine).filter(OCREngine.id == engine_id).first()
    
    if not engine:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OCR引擎不存在"
        )
    
    try:
        changes = {}
        
        if update_data.display_name is not None:
            old_name = engine.display_name
            engine.display_name = update_data.display_name
            changes["display_name"] = {"old": old_name, "new": update_data.display_name}
        
        if update_data.is_enabled is not None:
            old_enabled = engine.is_enabled
            engine.is_enabled = update_data.is_enabled
            changes["is_enabled"] = {"old": old_enabled, "new": update_data.is_enabled}
        
        if update_data.priority is not None:
            old_priority = engine.priority
            engine.priority = update_data.priority
            changes["priority"] = {"old": old_priority, "new": update_data.priority}
        
        if update_data.cost_per_page is not None:
            old_cost = engine.cost_per_page
            engine.cost_per_page = update_data.cost_per_page
            changes["cost_per_page"] = {"old": old_cost, "new": update_data.cost_per_page}
        
        if update_data.max_requests_per_minute is not None:
            old_max = engine.max_requests_per_minute
            engine.max_requests_per_minute = update_data.max_requests_per_minute
            changes["max_requests_per_minute"] = {"old": old_max, "new": update_data.max_requests_per_minute}
        
        if update_data.config is not None:
            old_config = engine.config
            engine.config = update_data.config
            changes["config"] = {"old": old_config, "new": update_data.config}
        
        engine.updated_at = datetime.now()
        db.commit()
        
        # 记录系统事件
        log_system_event(
            event_type="ocr_engine_updated",
            details={
                "engine_id": engine_id,
                "engine_name": engine.name,
                "changes": changes,
                "admin_id": admin_user.id
            }
        )
        
        return {
            "message": "OCR引擎配置已更新",
            "changes": changes
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新OCR引擎配置失败"
        )


@router.post("/cleanup/system")
async def system_cleanup(
    days: int = Query(30, ge=1, le=365, description="清理多少天前的数据"),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """系统数据清理"""
    try:
        from pathlib import Path
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 清理旧文件
        old_files = db.query(FileModel).filter(
            FileModel.upload_time < cutoff_date,
            FileModel.status.in_(["completed", "failed"])
        ).all()
        
        deleted_files = 0
        freed_space = 0
        
        for file_record in old_files:
            try:
                file_path = Path(file_record.file_path)
                if file_path.exists():
                    freed_space += file_path.stat().st_size
                    file_path.unlink()
                
                db.delete(file_record)
                deleted_files += 1
                
            except Exception:
                continue
        
        # 清理旧的API使用记录
        old_api_usage = db.query(APIUsage).filter(
            APIUsage.created_at < cutoff_date
        ).delete()
        
        # 清理失败的OCR任务
        failed_tasks = db.query(OCRTask).filter(
            OCRTask.created_at < cutoff_date,
            OCRTask.status == "failed"
        ).delete()
        
        db.commit()
        
        # 记录系统事件
        log_system_event(
            event_type="system_cleanup",
            details={
                "deleted_files": deleted_files,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2),
                "deleted_api_records": old_api_usage,
                "deleted_failed_tasks": failed_tasks,
                "cutoff_days": days,
                "admin_id": admin_user.id
            }
        )
        
        return {
            "message": "系统清理完成",
            "deleted_files": deleted_files,
            "freed_space_mb": round(freed_space / 1024 / 1024, 2),
            "deleted_api_records": old_api_usage,
            "deleted_failed_tasks": failed_tasks
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="系统清理失败"
        )


@router.get("/logs/security")
async def get_security_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    event_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=30),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """获取安全日志"""
    try:
        # 这里应该从日志系统中获取安全日志
        # 由于我们使用的是文件日志，这里返回模拟数据
        # 在实际实现中，可以集成ELK或其他日志系统
        
        return {
            "message": "安全日志功能需要集成专门的日志系统",
            "suggestion": "建议集成ELK Stack或其他日志管理系统来查看详细的安全日志"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取安全日志失败"
        )


@router.post("/maintenance")
async def toggle_maintenance_mode(
    enabled: bool,
    message: Optional[str] = None,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """切换维护模式"""
    try:
        # 更新系统配置
        maintenance_config = db.query(SystemConfig).filter(
            SystemConfig.key == "maintenance_mode"
        ).first()
        
        if not maintenance_config:
            maintenance_config = SystemConfig(
                key="maintenance_mode",
                value=str(enabled).lower(),
                description="系统维护模式"
            )
            db.add(maintenance_config)
        else:
            maintenance_config.value = str(enabled).lower()
            maintenance_config.updated_at = datetime.now()
        
        # 设置维护消息
        if message:
            message_config = db.query(SystemConfig).filter(
                SystemConfig.key == "maintenance_message"
            ).first()
            
            if not message_config:
                message_config = SystemConfig(
                    key="maintenance_message",
                    value=message,
                    description="维护模式消息"
                )
                db.add(message_config)
            else:
                message_config.value = message
                message_config.updated_at = datetime.now()
        
        db.commit()
        
        # 记录系统事件
        log_system_event(
            event_type="maintenance_mode_toggled",
            details={
                "enabled": enabled,
                "message": message,
                "admin_id": admin_user.id
            }
        )
        
        return {
            "message": f"维护模式已{'启用' if enabled else '禁用'}",
            "maintenance_enabled": enabled,
            "maintenance_message": message
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="切换维护模式失败"
        )