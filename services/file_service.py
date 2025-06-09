import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import mimetypes

from models import File, User
from utils.security import generate_secure_filename, calculate_file_hash, sanitize_filename
from utils.logger import setup_logger, log_user_activity
from config import settings, SUPPORTED_FILE_TYPES


class FileService:
    """文件服务类"""
    
    def __init__(self):
        self.logger = setup_logger("file_service")
        self.upload_dir = Path(settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_user_upload_dir(self, user_id: int) -> Path:
        """获取用户上传目录"""
        user_dir = self.upload_dir / f"user_{user_id}"
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def _get_file_type(self, filename: str) -> str:
        """获取文件类型"""
        ext = Path(filename).suffix.lower()
        if ext == '.pdf':
            return 'pdf'
        elif ext in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.webp']:
            return 'image'
        else:
            return 'unknown'
    
    def _get_mime_type(self, filename: str) -> str:
        """获取MIME类型"""
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type
        
        # 手动映射一些常见类型
        ext = Path(filename).suffix.lower()
        return SUPPORTED_FILE_TYPES.get(ext, 'application/octet-stream')
    
    def validate_file(self, filename: str, file_content: bytes) -> Dict[str, Any]:
        """验证文件"""
        try:
            # 检查文件扩展名
            ext = Path(filename).suffix.lower()
            if ext not in settings.allowed_extensions:
                return {
                    "valid": False,
                    "error": f"不支持的文件类型: {ext}",
                    "code": "UNSUPPORTED_FILE_TYPE"
                }
            
            # 检查文件大小
            if len(file_content) > settings.max_file_size:
                return {
                    "valid": False,
                    "error": f"文件大小超过限制: {settings.max_file_size / 1024 / 1024:.1f}MB",
                    "code": "FILE_TOO_LARGE"
                }
            
            # 检查文件内容（简单的魔数检查）
            if not self._validate_file_content(file_content, ext):
                return {
                    "valid": False,
                    "error": "文件内容与扩展名不匹配",
                    "code": "INVALID_FILE_CONTENT"
                }
            
            return {"valid": True}
            
        except Exception as e:
            self.logger.error(f"文件验证失败: {e}")
            return {
                "valid": False,
                "error": "文件验证失败",
                "code": "VALIDATION_ERROR"
            }
    
    def _validate_file_content(self, file_content: bytes, ext: str) -> bool:
        """验证文件内容"""
        if len(file_content) < 4:
            return False
        
        # 检查文件魔数
        magic_numbers = {
            '.pdf': [b'%PDF'],
            '.png': [b'\x89PNG'],
            '.jpg': [b'\xff\xd8\xff'],
            '.jpeg': [b'\xff\xd8\xff'],
            '.tiff': [b'II*\x00', b'MM\x00*'],
            '.bmp': [b'BM'],
            '.webp': [b'RIFF']
        }
        
        expected_magic = magic_numbers.get(ext, [])
        if not expected_magic:
            return True  # 未知类型，跳过验证
        
        for magic in expected_magic:
            if file_content.startswith(magic):
                return True
        
        return False
    
    async def save_uploaded_file(
        self, 
        db: Session, 
        user_id: int, 
        original_filename: str, 
        file_content: bytes
    ) -> File:
        """保存上传的文件"""
        try:
            # 验证文件
            validation_result = self.validate_file(original_filename, file_content)
            if not validation_result["valid"]:
                raise ValueError(validation_result["error"])
            
            # 清理文件名
            clean_filename = sanitize_filename(original_filename)
            
            # 生成安全的文件名
            secure_filename = generate_secure_filename(clean_filename, user_id)
            
            # 获取用户上传目录
            user_dir = self._get_user_upload_dir(user_id)
            file_path = user_dir / secure_filename
            
            # 计算文件哈希
            file_hash = calculate_file_hash(file_content)
            
            # 检查是否已存在相同文件
            existing_file = db.query(File).filter(
                File.user_id == user_id,
                File.file_hash == file_hash
            ).first()
            
            if existing_file:
                self.logger.info(f"文件已存在，返回现有记录: {existing_file.id}")
                return existing_file
            
            # 保存文件到磁盘
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # 创建数据库记录
            file_record = File(
                user_id=user_id,
                filename=secure_filename,
                original_filename=clean_filename,
                file_path=str(file_path),
                file_size=len(file_content),
                file_type=self._get_file_type(clean_filename),
                mime_type=self._get_mime_type(clean_filename),
                file_hash=file_hash,
                status="uploaded"
            )
            
            db.add(file_record)
            db.commit()
            db.refresh(file_record)
            
            # 记录日志
            log_user_activity(
                user_id=user_id,
                activity="file_uploaded",
                details={
                    "file_id": file_record.id,
                    "filename": clean_filename,
                    "file_size": len(file_content),
                    "file_type": file_record.file_type
                }
            )
            
            self.logger.info(f"文件上传成功: {clean_filename} (ID: {file_record.id})")
            return file_record
            
        except ValueError:
            raise
        except Exception as e:
            db.rollback()
            # 清理已保存的文件
            if 'file_path' in locals() and file_path.exists():
                file_path.unlink()
            
            self.logger.error(f"保存文件失败: {e}")
            raise ValueError("文件保存失败")
    
    def get_user_files(
        self, 
        db: Session, 
        user_id: int, 
        page: int = 1, 
        size: int = 20,
        file_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取用户文件列表"""
        try:
            query = db.query(File).filter(File.user_id == user_id)
            
            # 添加过滤条件
            if file_type:
                query = query.filter(File.file_type == file_type)
            if status:
                query = query.filter(File.status == status)
            
            # 计算总数
            total = query.count()
            
            # 分页查询
            offset = (page - 1) * size
            files = query.order_by(File.upload_time.desc()).offset(offset).limit(size).all()
            
            return {
                "files": [
                    {
                        "id": file.id,
                        "filename": file.original_filename,
                        "file_size": file.file_size,
                        "file_type": file.file_type,
                        "status": file.status,
                        "upload_time": file.upload_time.isoformat(),
                        "processed_at": file.processed_at.isoformat() if file.processed_at else None
                    }
                    for file in files
                ],
                "total": total,
                "page": page,
                "size": size,
                "pages": (total + size - 1) // size
            }
            
        except Exception as e:
            self.logger.error(f"获取用户文件列表失败: {e}")
            raise ValueError("获取文件列表失败")
    
    def get_file_by_id(self, db: Session, file_id: int, user_id: int = None) -> Optional[File]:
        """根据ID获取文件"""
        query = db.query(File).filter(File.id == file_id)
        if user_id:
            query = query.filter(File.user_id == user_id)
        return query.first()
    
    def delete_file(self, db: Session, file_id: int, user_id: int) -> bool:
        """删除文件"""
        try:
            file_record = db.query(File).filter(
                File.id == file_id,
                File.user_id == user_id
            ).first()
            
            if not file_record:
                raise ValueError("文件不存在")
            
            # 删除磁盘文件
            file_path = Path(file_record.file_path)
            if file_path.exists():
                file_path.unlink()
            
            # 删除数据库记录
            db.delete(file_record)
            db.commit()
            
            # 记录日志
            log_user_activity(
                user_id=user_id,
                activity="file_deleted",
                details={
                    "file_id": file_id,
                    "filename": file_record.original_filename
                }
            )
            
            self.logger.info(f"文件删除成功: {file_record.original_filename} (ID: {file_id})")
            return True
            
        except ValueError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            self.logger.error(f"删除文件失败: {e}")
            raise ValueError("删除文件失败")
    
    def update_file_status(self, db: Session, file_id: int, status: str) -> bool:
        """更新文件状态"""
        try:
            file_record = db.query(File).filter(File.id == file_id).first()
            if not file_record:
                return False
            
            old_status = file_record.status
            file_record.status = status
            
            if status == "completed":
                file_record.processed_at = datetime.now()
            
            db.commit()
            
            self.logger.info(f"文件状态更新: {file_id} {old_status} -> {status}")
            return True
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"更新文件状态失败: {e}")
            return False
    
    def get_file_content(self, file_path: str) -> bytes:
        """读取文件内容"""
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"读取文件内容失败: {e}")
            raise ValueError("读取文件失败")
    
    def cleanup_old_files(self, db: Session, days: int = 30) -> int:
        """清理旧文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # 查找过期文件
            old_files = db.query(File).filter(
                File.upload_time < cutoff_date,
                File.status.in_(["completed", "failed"])
            ).all()
            
            deleted_count = 0
            for file_record in old_files:
                try:
                    # 删除磁盘文件
                    file_path = Path(file_record.file_path)
                    if file_path.exists():
                        file_path.unlink()
                    
                    # 删除数据库记录
                    db.delete(file_record)
                    deleted_count += 1
                    
                except Exception as e:
                    self.logger.error(f"删除过期文件失败: {file_record.id} - {e}")
                    continue
            
            db.commit()
            
            self.logger.info(f"清理完成，删除了 {deleted_count} 个过期文件")
            return deleted_count
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"清理旧文件失败: {e}")
            return 0
    
    def get_storage_stats(self, db: Session, user_id: int = None) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            query = db.query(File)
            if user_id:
                query = query.filter(File.user_id == user_id)
            
            files = query.all()
            
            total_files = len(files)
            total_size = sum(file.file_size for file in files)
            
            # 按类型统计
            type_stats = {}
            for file in files:
                file_type = file.file_type
                if file_type not in type_stats:
                    type_stats[file_type] = {"count": 0, "size": 0}
                type_stats[file_type]["count"] += 1
                type_stats[file_type]["size"] += file.file_size
            
            # 按状态统计
            status_stats = {}
            for file in files:
                status = file.status
                if status not in status_stats:
                    status_stats[status] = 0
                status_stats[status] += 1
            
            return {
                "total_files": total_files,
                "total_size": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
                "type_stats": type_stats,
                "status_stats": status_stats
            }
            
        except Exception as e:
            self.logger.error(f"获取存储统计失败: {e}")
            return {}