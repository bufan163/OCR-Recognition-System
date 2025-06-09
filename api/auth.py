from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime, timedelta

from database import get_db
from models import User
from services.auth_service import AuthService
from utils.security import get_current_user, verify_password_strength
from utils.logger import log_user_activity, log_security_event
from config import settings

router = APIRouter(prefix="/auth", tags=["认证"])
security = HTTPBearer()
auth_service = AuthService()


class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    
    @validator('username')
    def validate_username(cls, v):
        if len(v) < 3 or len(v) > 50:
            raise ValueError('用户名长度必须在3-50个字符之间')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('用户名只能包含字母、数字、下划线和连字符')
        return v
    
    @validator('password')
    def validate_password(cls, v):
        result = verify_password_strength(v)
        if not result['valid']:
            raise ValueError(result['message'])
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        result = verify_password_strength(v)
        if not result['valid']:
            raise ValueError(result['message'])
        return v


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def validate_new_password(cls, v):
        result = verify_password_strength(v)
        if not result['valid']:
            raise ValueError(result['message'])
        return v


class UserResponse(BaseModel):
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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """用户注册"""
    try:
        # 检查用户名是否已存在
        existing_user = auth_service.get_user_by_username(db, user_data.username)
        if existing_user:
            log_security_event(
                event="registration_failed",
                details={"username": user_data.username, "reason": "username_exists"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        
        # 检查邮箱是否已存在
        existing_email = auth_service.get_user_by_email(db, user_data.email)
        if existing_email:
            log_security_event(
                event="registration_failed",
                details={"email": user_data.email, "reason": "email_exists"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        
        # 创建用户
        user = auth_service.create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password,
            full_name=user_data.full_name
        )
        
        # 记录用户活动
        log_user_activity(
            user_id=user.id,
            activity="user_registered",
            details={"username": user.username, "email": user.email}
        )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            event="registration_error",
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """用户登录"""
    try:
        # 验证用户凭据
        user = auth_service.authenticate_user(
            db=db,
            username=user_data.username,
            password=user_data.password
        )
        
        if not user:
            log_security_event(
                event="login_failed",
                details={"username": user_data.username, "reason": "invalid_credentials"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            log_security_event(
                event="login_failed",
                details={"username": user_data.username, "reason": "account_disabled"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="账户已被禁用"
            )
        
        # 生成访问令牌
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = auth_service.create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires
        )
        
        # 更新最后登录时间
        user.last_login = datetime.now()
        db.commit()
        
        # 记录用户活动
        log_user_activity(
            user_id=user.id,
            activity="user_login",
            details={"username": user.username}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            event="login_error",
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """用户登出"""
    try:
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="user_logout",
            details={"username": current_user.username}
        )
        
        return {"message": "登出成功"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登出失败"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """获取当前用户信息"""
    return current_user


@router.put("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """修改密码"""
    try:
        # 验证旧密码
        if not auth_service.verify_password(password_data.old_password, current_user.hashed_password):
            log_security_event(
                event="password_change_failed",
                details={"user_id": current_user.id, "reason": "invalid_old_password"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码错误"
            )
        
        # 检查新密码是否与旧密码相同
        if password_data.old_password == password_data.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="新密码不能与旧密码相同"
            )
        
        # 更新密码
        success = auth_service.change_password(
            db=db,
            user_id=current_user.id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码修改失败"
            )
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="password_changed",
            details={"username": current_user.username}
        )
        
        log_security_event(
            event="password_changed",
            details={"user_id": current_user.id}
        )
        
        return {"message": "密码修改成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            event="password_change_error",
            details={"user_id": current_user.id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码修改失败，请稍后重试"
        )


@router.post("/reset-password")
async def reset_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)
):
    """请求密码重置"""
    try:
        # 查找用户
        user = auth_service.get_user_by_email(db, reset_data.email)
        if not user:
            # 为了安全，即使用户不存在也返回成功消息
            return {"message": "如果该邮箱已注册，您将收到密码重置邮件"}
        
        # 生成重置令牌（这里简化处理，实际应该发送邮件）
        reset_token = auth_service.create_password_reset_token(user.email)
        
        # 记录安全事件
        log_security_event(
            event="password_reset_requested",
            details={"user_id": user.id, "email": reset_data.email}
        )
        
        # TODO: 发送重置邮件
        # send_password_reset_email(user.email, reset_token)
        
        return {
            "message": "如果该邮箱已注册，您将收到密码重置邮件",
            "reset_token": reset_token  # 仅用于测试，生产环境应通过邮件发送
        }
        
    except Exception as e:
        log_security_event(
            event="password_reset_error",
            details={"email": reset_data.email, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码重置请求失败，请稍后重试"
        )


@router.post("/reset-password/confirm")
async def confirm_password_reset(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """确认密码重置"""
    try:
        # 验证重置令牌
        email = auth_service.verify_password_reset_token(reset_data.token)
        if not email:
            log_security_event(
                event="password_reset_failed",
                details={"reason": "invalid_token"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="重置令牌无效或已过期"
            )
        
        # 查找用户
        user = auth_service.get_user_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户不存在"
            )
        
        # 更新密码
        user.hashed_password = auth_service.get_password_hash(reset_data.new_password)
        db.commit()
        
        # 记录用户活动和安全事件
        log_user_activity(
            user_id=user.id,
            activity="password_reset",
            details={"username": user.username}
        )
        
        log_security_event(
            event="password_reset_completed",
            details={"user_id": user.id}
        )
        
        return {"message": "密码重置成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            event="password_reset_error",
            details={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="密码重置失败，请稍后重试"
        )


@router.put("/profile")
async def update_profile(
    full_name: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户资料"""
    try:
        updated = False
        
        if full_name is not None:
            current_user.full_name = full_name
            updated = True
        
        if updated:
            db.commit()
            
            # 记录用户活动
            log_user_activity(
                user_id=current_user.id,
                activity="profile_updated",
                details={"username": current_user.username}
            )
        
        return {"message": "资料更新成功" if updated else "没有更新任何信息"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="资料更新失败"
        )


@router.delete("/account")
async def delete_account(
    password: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除账户"""
    try:
        # 验证密码
        if not auth_service.verify_password(password, current_user.hashed_password):
            log_security_event(
                event="account_deletion_failed",
                details={"user_id": current_user.id, "reason": "invalid_password"}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码错误"
            )
        
        # 停用账户（软删除）
        success = auth_service.deactivate_user(db, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="账户删除失败"
            )
        
        # 记录用户活动和安全事件
        log_user_activity(
            user_id=current_user.id,
            activity="account_deleted",
            details={"username": current_user.username}
        )
        
        log_security_event(
            event="account_deleted",
            details={"user_id": current_user.id}
        )
        
        return {"message": "账户已删除"}
        
    except HTTPException:
        raise
    except Exception as e:
        log_security_event(
            event="account_deletion_error",
            details={"user_id": current_user.id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="账户删除失败，请稍后重试"
        )