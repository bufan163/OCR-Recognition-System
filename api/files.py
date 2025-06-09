from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from database import get_db
from models import User, File as FileModel
from services.file_service import FileService
from utils.security import get_current_user
from utils.logger import log_user_activity
from config import settings

router = APIRouter(prefix="/files", tags=["文件管理"])
file_service = FileService()


class FileResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    mime_type: str
    status: str
    upload_time: datetime
    processed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    files: List[FileResponse]
    total: int
    page: int
    size: int
    pages: int


class StorageStatsResponse(BaseModel):
    total_files: int
    total_size: int
    total_size_mb: float
    type_stats: dict
    status_stats: dict


@router.post("/upload", response_model=FileResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """上传文件"""
    try:
        # 检查文件是否为空
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要上传的文件"
            )
        
        # 读取文件内容
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
        
        return file_record
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件上传失败"
        )


@router.post("/upload/batch", response_model=List[FileResponse])
async def upload_multiple_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量上传文件"""
    if len(files) > settings.max_batch_upload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"一次最多只能上传 {settings.max_batch_upload} 个文件"
        )
    
    uploaded_files = []
    failed_files = []
    
    for file in files:
        try:
            if not file.filename:
                failed_files.append({"filename": "未知", "error": "文件名为空"})
                continue
            
            file_content = await file.read()
            
            if len(file_content) == 0:
                failed_files.append({"filename": file.filename, "error": "文件内容为空"})
                continue
            
            file_record = await file_service.save_uploaded_file(
                db=db,
                user_id=current_user.id,
                original_filename=file.filename,
                file_content=file_content
            )
            
            uploaded_files.append(file_record)
            
        except Exception as e:
            failed_files.append({"filename": file.filename, "error": str(e)})
            continue
    
    # 记录用户活动
    log_user_activity(
        user_id=current_user.id,
        activity="batch_upload",
        details={
            "uploaded_count": len(uploaded_files),
            "failed_count": len(failed_files),
            "failed_files": failed_files
        }
    )
    
    if failed_files:
        raise HTTPException(
            status_code=status.HTTP_207_MULTI_STATUS,
            detail={
                "message": f"部分文件上传失败: {len(uploaded_files)} 成功, {len(failed_files)} 失败",
                "uploaded_files": uploaded_files,
                "failed_files": failed_files
            }
        )
    
    return uploaded_files


@router.get("/", response_model=FileListResponse)
async def get_user_files(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页数量"),
    file_type: Optional[str] = Query(None, description="文件类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取用户文件列表"""
    try:
        result = file_service.get_user_files(
            db=db,
            user_id=current_user.id,
            page=page,
            size=size,
            file_type=file_type,
            status=status
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文件列表失败"
        )


@router.get("/{file_id}", response_model=FileResponse)
async def get_file_info(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取文件详细信息"""
    file_record = file_service.get_file_by_id(db, file_id, current_user.id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    return file_record


@router.get("/{file_id}/download")
async def download_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """下载文件"""
    file_record = file_service.get_file_by_id(db, file_id, current_user.id)
    
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )
    
    file_path = Path(file_record.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已被删除"
        )
    
    # 记录用户活动
    log_user_activity(
        user_id=current_user.id,
        activity="file_downloaded",
        details={
            "file_id": file_id,
            "filename": file_record.original_filename
        }
    )
    
    return FileResponse(
        path=file_path,
        filename=file_record.original_filename,
        media_type=file_record.mime_type
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除文件"""
    try:
        success = file_service.delete_file(db, file_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        
        return {"message": "文件删除成功"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件删除失败"
        )


@router.delete("/batch")
async def delete_multiple_files(
    file_ids: List[int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """批量删除文件"""
    if len(file_ids) > 50:  # 限制批量删除数量
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="一次最多只能删除50个文件"
        )
    
    deleted_files = []
    failed_files = []
    
    for file_id in file_ids:
        try:
            success = file_service.delete_file(db, file_id, current_user.id)
            if success:
                deleted_files.append(file_id)
            else:
                failed_files.append({"file_id": file_id, "error": "文件不存在"})
        except Exception as e:
            failed_files.append({"file_id": file_id, "error": str(e)})
    
    # 记录用户活动
    log_user_activity(
        user_id=current_user.id,
        activity="batch_delete",
        details={
            "deleted_count": len(deleted_files),
            "failed_count": len(failed_files),
            "deleted_files": deleted_files,
            "failed_files": failed_files
        }
    )
    
    return {
        "message": f"删除完成: {len(deleted_files)} 成功, {len(failed_files)} 失败",
        "deleted_files": deleted_files,
        "failed_files": failed_files
    }


@router.get("/stats/storage", response_model=StorageStatsResponse)
async def get_storage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取存储统计信息"""
    try:
        stats = file_service.get_storage_stats(db, current_user.id)
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取存储统计失败"
        )


@router.post("/validate")
async def validate_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """验证文件（不保存）"""
    try:
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请选择要验证的文件"
            )
        
        # 读取文件内容
        file_content = await file.read()
        
        # 验证文件
        validation_result = file_service.validate_file(file.filename, file_content)
        
        if validation_result["valid"]:
            return {
                "valid": True,
                "message": "文件验证通过",
                "file_info": {
                    "filename": file.filename,
                    "size": len(file_content),
                    "size_mb": round(len(file_content) / 1024 / 1024, 2)
                }
            }
        else:
            return {
                "valid": False,
                "error": validation_result["error"],
                "code": validation_result["code"]
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件验证失败"
        )


@router.get("/types/supported")
async def get_supported_file_types():
    """获取支持的文件类型"""
    return {
        "supported_extensions": list(settings.allowed_extensions),
        "max_file_size": settings.max_file_size,
        "max_file_size_mb": round(settings.max_file_size / 1024 / 1024, 2),
        "file_types": {
            "pdf": {
                "extensions": [".pdf"],
                "description": "PDF文档",
                "max_pages": settings.max_pdf_pages
            },
            "image": {
                "extensions": [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"],
                "description": "图像文件",
                "supported_formats": "PNG, JPEG, TIFF, BMP, WebP"
            }
        }
    }


@router.post("/cleanup/user")
async def cleanup_user_files(
    days: int = Query(30, ge=1, le=365, description="清理多少天前的文件"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """清理用户的旧文件"""
    try:
        # 只允许清理已完成或失败的文件
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        old_files = db.query(FileModel).filter(
            FileModel.user_id == current_user.id,
            FileModel.upload_time < cutoff_date,
            FileModel.status.in_(["completed", "failed"])
        ).all()
        
        deleted_count = 0
        freed_space = 0
        
        for file_record in old_files:
            try:
                file_path = Path(file_record.file_path)
                if file_path.exists():
                    freed_space += file_path.stat().st_size
                    file_path.unlink()
                
                db.delete(file_record)
                deleted_count += 1
                
            except Exception as e:
                continue
        
        db.commit()
        
        # 记录用户活动
        log_user_activity(
            user_id=current_user.id,
            activity="user_cleanup",
            details={
                "deleted_files": deleted_count,
                "freed_space_mb": round(freed_space / 1024 / 1024, 2),
                "cutoff_days": days
            }
        )
        
        return {
            "message": "清理完成",
            "deleted_files": deleted_count,
            "freed_space_mb": round(freed_space / 1024 / 1024, 2)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="文件清理失败"
        )