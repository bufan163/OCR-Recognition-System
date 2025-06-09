from datetime import datetime, timedelta
from typing import Optional, Union
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging

from config import settings
from database import get_db
from models import User

# 设置日志
logger = logging.getLogger(__name__)

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer认证
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"密码验证失败: {e}")
        return False


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    try:
        return pwd_context.hash(password)
    except Exception as e:
        logger.error(f"密码哈希生成失败: {e}")
        raise ValueError("密码处理失败")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        return encoded_jwt
    except Exception as e:
        logger.error(f"令牌创建失败: {e}")
        raise ValueError("令牌创建失败")


def verify_token(token: str) -> Optional[dict]:
    """验证令牌"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username: str = payload.get("sub")
        if username is None:
            return None
        return payload
    except JWTError as e:
        logger.warning(f"令牌验证失败: {e}")
        return None
    except Exception as e:
        logger.error(f"令牌验证异常: {e}")
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 验证令牌
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # 查询用户
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise credentials_exception
        
        # 检查用户状态
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="用户账户已被禁用"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取当前用户失败: {e}")
        raise credentials_exception


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户账户已被禁用"
        )
    return current_user


def check_user_permissions(user: User, required_plan: str = "free") -> bool:
    """检查用户权限"""
    plan_hierarchy = {
        "free": 0,
        "premium": 1,
        "enterprise": 2
    }
    
    user_level = plan_hierarchy.get(user.plan_type, 0)
    required_level = plan_hierarchy.get(required_plan, 0)
    
    return user_level >= required_level


def require_plan(required_plan: str):
    """装饰器：要求特定用户计划"""
    def decorator(current_user: User = Depends(get_current_user)):
        if not check_user_permissions(current_user, required_plan):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"需要 {required_plan} 计划才能访问此功能"
            )
        return current_user
    return decorator


def validate_password_strength(password: str) -> bool:
    """验证密码强度"""
    if len(password) < 8:
        return False
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    return sum([has_upper, has_lower, has_digit, has_special]) >= 3


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除危险字符"""
    import re
    import os
    
    # 移除路径分隔符和危险字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # 移除控制字符
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # 限制长度
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]
    
    return name + ext


def generate_secure_filename(original_filename: str, user_id: int) -> str:
    """生成安全的文件名"""
    import uuid
    import os
    from datetime import datetime
    
    # 获取文件扩展名
    _, ext = os.path.splitext(original_filename)
    
    # 生成唯一文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    
    return f"user_{user_id}_{timestamp}_{unique_id}{ext}"


def check_file_type(filename: str, allowed_extensions: list) -> bool:
    """检查文件类型"""
    import os
    
    _, ext = os.path.splitext(filename.lower())
    return ext in [e.lower() for e in allowed_extensions]


def calculate_file_hash(file_content: bytes) -> str:
    """计算文件哈希值"""
    import hashlib
    
    return hashlib.md5(file_content).hexdigest()