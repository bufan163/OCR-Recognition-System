from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import re

from models import User, UserQuota
from utils.security import (
    get_password_hash, 
    verify_password, 
    create_access_token,
    validate_password_strength
)
from utils.logger import setup_logger, log_user_activity, log_security_event
from config import settings


class AuthService:
    """认证服务类"""
    
    def __init__(self):
        self.logger = setup_logger("auth_service")
    
    def validate_email(self, email: str) -> bool:
        """验证邮箱格式"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_username(self, username: str) -> bool:
        """验证用户名格式"""
        # 用户名长度3-50，只能包含字母、数字、下划线
        pattern = r'^[a-zA-Z0-9_]{3,50}$'
        return re.match(pattern, username) is not None
    
    async def register_user(
        self, 
        db: Session, 
        username: str, 
        email: str, 
        password: str,
        plan_type: str = "free",
        is_admin: bool = False
    ) -> User:
        """用户注册"""
        try:
            # 验证输入
            if not self.validate_username(username):
                raise ValueError("用户名格式不正确，只能包含字母、数字、下划线，长度3-50位")
            
            if not self.validate_email(email):
                raise ValueError("邮箱格式不正确")
            
            if not validate_password_strength(password):
                raise ValueError("密码强度不够，至少8位且包含大小写字母、数字、特殊字符中的3种")
            
            # 检查用户名和邮箱是否已存在
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                if existing_user.username == username:
                    raise ValueError("用户名已存在")
                else:
                    raise ValueError("邮箱已被注册")
            
            # 创建用户
            hashed_password = get_password_hash(password)
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                plan_type=plan_type,
                api_quota=settings.free_user_daily_quota if plan_type == "free" else settings.premium_user_daily_quota,
                is_admin=is_admin
            )
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # 创建用户配额记录
            await self._create_user_quota(db, user.id, plan_type)
            
            # 记录日志
            log_user_activity(
                user_id=user.id,
                activity="user_registered",
                details={"username": username, "email": email, "plan_type": plan_type}
            )
            
            self.logger.info(f"用户注册成功: {username} ({email})")
            return user
            
        except IntegrityError as e:
            db.rollback()
            self.logger.error(f"用户注册数据库错误: {e}")
            raise ValueError("用户名或邮箱已存在")
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            self.logger.error(f"用户注册失败: {e}")
            raise ValueError("注册失败，请稍后重试")
    
    async def authenticate_user(
        self, 
        db: Session, 
        username: str, 
        password: str,
        ip_address: str = None
    ) -> Dict[str, Any]:
        """用户认证"""
        try:
            # 查找用户
            user = db.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if not user:
                log_security_event(
                    event_type="login_failed",
                    ip_address=ip_address,
                    details={"username": username, "reason": "user_not_found"}
                )
                raise ValueError("用户名或密码错误")
            
            # 检查用户状态
            if not user.is_active:
                log_security_event(
                    event_type="login_failed",
                    user_id=user.id,
                    ip_address=ip_address,
                    details={"username": username, "reason": "account_disabled"}
                )
                raise ValueError("账户已被禁用")
            
            # 验证密码
            if not verify_password(password, user.hashed_password):
                log_security_event(
                    event_type="login_failed",
                    user_id=user.id,
                    ip_address=ip_address,
                    details={"username": username, "reason": "wrong_password"}
                )
                raise ValueError("用户名或密码错误")
            
            # 创建访问令牌
            access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
            access_token = create_access_token(
                data={"sub": user.username, "user_id": user.id},
                expires_delta=access_token_expires
            )
            
            # 记录成功登录
            log_user_activity(
                user_id=user.id,
                activity="user_login",
                details={"username": username, "ip_address": ip_address}
            )
            
            self.logger.info(f"用户登录成功: {username}")
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": settings.access_token_expire_minutes * 60,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "plan_type": user.plan_type
                }
            }
            
        except ValueError:
            raise
        except Exception as e:
            self.logger.error(f"用户认证失败: {e}")
            raise ValueError("登录失败，请稍后重试")
    
    async def change_password(
        self, 
        db: Session, 
        user_id: int, 
        old_password: str, 
        new_password: str
    ) -> bool:
        """修改密码"""
        try:
            # 获取用户
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("用户不存在")
            
            # 验证旧密码
            if not verify_password(old_password, user.hashed_password):
                log_security_event(
                    event_type="password_change_failed",
                    user_id=user_id,
                    details={"reason": "wrong_old_password"}
                )
                raise ValueError("原密码错误")
            
            # 验证新密码强度
            if not validate_password_strength(new_password):
                raise ValueError("新密码强度不够")
            
            # 更新密码
            user.hashed_password = get_password_hash(new_password)
            db.commit()
            
            # 记录日志
            log_user_activity(
                user_id=user_id,
                activity="password_changed"
            )
            
            self.logger.info(f"用户 {user.username} 修改密码成功")
            return True
            
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            self.logger.error(f"修改密码失败: {e}")
            raise ValueError("修改密码失败")
    
    async def update_user_plan(
        self, 
        db: Session, 
        user_id: int, 
        new_plan: str
    ) -> User:
        """更新用户计划"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("用户不存在")
            
            old_plan = user.plan_type
            user.plan_type = new_plan
            
            # 更新配额
            if new_plan == "free":
                user.api_quota = settings.free_user_daily_quota
            elif new_plan == "premium":
                user.api_quota = settings.premium_user_daily_quota
            
            db.commit()
            db.refresh(user)
            
            # 更新配额记录
            await self._update_user_quota(db, user_id, new_plan)
            
            # 记录日志
            log_user_activity(
                user_id=user_id,
                activity="plan_updated",
                details={"old_plan": old_plan, "new_plan": new_plan}
            )
            
            self.logger.info(f"用户 {user.username} 计划更新: {old_plan} -> {new_plan}")
            return user
            
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            self.logger.error(f"更新用户计划失败: {e}")
            raise ValueError("更新计划失败")
    
    async def deactivate_user(self, db: Session, user_id: int) -> bool:
        """停用用户账户"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("用户不存在")
            
            user.is_active = False
            db.commit()
            
            # 记录日志
            log_user_activity(
                user_id=user_id,
                activity="account_deactivated"
            )
            
            self.logger.info(f"用户 {user.username} 账户已停用")
            return True
            
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            self.logger.error(f"停用用户失败: {e}")
            raise ValueError("停用账户失败")
    
    async def _create_user_quota(self, db: Session, user_id: int, plan_type: str):
        """创建用户配额记录"""
        try:
            # 每日配额
            daily_quota = UserQuota(
                user_id=user_id,
                quota_type="daily",
                quota_limit=settings.free_user_daily_quota if plan_type == "free" else settings.premium_user_daily_quota,
                quota_used=0,
                reset_time=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            )
            
            # 月度配额
            monthly_limit = settings.free_user_daily_quota * 30 if plan_type == "free" else settings.premium_user_daily_quota * 30
            monthly_quota = UserQuota(
                user_id=user_id,
                quota_type="monthly",
                quota_limit=monthly_limit,
                quota_used=0,
                reset_time=datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=32)
            )
            
            db.add(daily_quota)
            db.add(monthly_quota)
            db.commit()
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"创建用户配额失败: {e}")
            raise
    
    async def _update_user_quota(self, db: Session, user_id: int, plan_type: str):
        """更新用户配额"""
        try:
            quotas = db.query(UserQuota).filter(UserQuota.user_id == user_id).all()
            
            for quota in quotas:
                if quota.quota_type == "daily":
                    quota.quota_limit = settings.free_user_daily_quota if plan_type == "free" else settings.premium_user_daily_quota
                elif quota.quota_type == "monthly":
                    quota.quota_limit = (settings.free_user_daily_quota * 30 if plan_type == "free" 
                                       else settings.premium_user_daily_quota * 30)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"更新用户配额失败: {e}")
            raise
    
    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """根据ID获取用户"""
        return db.query(User).filter(User.id == user_id).first()
    
    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return db.query(User).filter(User.username == username).first()
    
    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        """根据邮箱获取用户"""
        return db.query(User).filter(User.email == email).first()