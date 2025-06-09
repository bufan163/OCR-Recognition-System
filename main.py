from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import os
import logging
from pathlib import Path

from config import settings
from database import engine, Base, get_db
from models import User, File as FileModel, OCRTask, OCRResult
from services.auth_service import AuthService
from services.file_service import FileService
from services.ocr_service import OCRService
from utils.security import get_current_user
from utils.logger import setup_logger

# 设置日志
logger = setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("正在启动OCR识别系统...")
    
    # 创建上传目录
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs("./logs", exist_ok=True)
    os.makedirs("./temp", exist_ok=True)
    
    # 创建数据库表
    Base.metadata.create_all(bind=engine)
    
    logger.info(f"OCR识别系统启动完成，监听端口: {settings.port}")
    
    yield
    
    # 关闭时执行
    logger.info("OCR识别系统正在关闭...")


# 创建FastAPI应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于多引擎的OCR文字识别系统，支持PDF和图片处理",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加可信主机中间件
if not settings.debug:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", settings.host]
    )

# 静态文件服务
if os.path.exists("./static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# 初始化服务
auth_service = AuthService()
file_service = FileService()
ocr_service = OCRService()


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用OCR识别系统",
        "version": settings.app_version,
        "docs": "/docs" if settings.debug else "文档已禁用"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "timestamp": "2024-01-01T00:00:00Z"
    }


# 用户认证相关API
@app.post("/api/auth/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db)
):
    """用户注册"""
    try:
        user = await auth_service.register_user(db, username, email, password)
        return {
            "message": "注册成功",
            "user_id": user.id,
            "username": user.username
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"注册失败: {e}")
        raise HTTPException(status_code=500, detail="注册失败")


@app.post("/api/auth/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db)
):
    """用户登录"""
    try:
        token_data = await auth_service.authenticate_user(db, username, password)
        return {
            "access_token": token_data["access_token"],
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(status_code=500, detail="登录失败")


# 文件上传API
@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    engine_preference: str = Form(default="auto"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """文件上传"""
    try:
        # 验证文件类型
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in settings.allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file_ext}"
            )
        
        # 验证文件大小
        file_content = await file.read()
        if len(file_content) > settings.max_file_size:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制: {settings.max_file_size / 1024 / 1024}MB"
            )
        
        # 保存文件
        saved_file = await file_service.save_uploaded_file(
            db, current_user.id, file.filename, file_content
        )
        
        # 创建OCR任务
        task = await ocr_service.create_ocr_task(
            db, saved_file.id, engine_preference
        )
        
        return {
            "message": "文件上传成功",
            "file_id": saved_file.id,
            "task_id": task.id,
            "filename": saved_file.filename,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail="文件上传失败")


# OCR处理API
@app.post("/api/ocr/process/{file_id}")
async def process_ocr(
    file_id: int,
    engine: str = Form(default="auto"),
    language: str = Form(default="chi_sim+eng"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """开始OCR处理"""
    try:
        # 验证文件所有权
        file_obj = db.query(FileModel).filter(
            FileModel.id == file_id,
            FileModel.user_id == current_user.id
        ).first()
        
        if not file_obj:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 启动OCR任务
        task = await ocr_service.start_ocr_processing(
            db, file_id, engine, language
        )
        
        return {
            "message": "OCR任务已启动",
            "task_id": task.id,
            "status": task.status,
            "estimated_time": "1-5分钟"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR处理失败: {e}")
        raise HTTPException(status_code=500, detail="OCR处理失败")


# 获取OCR结果API
@app.get("/api/ocr/result/{task_id}")
async def get_ocr_result(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """获取OCR结果"""
    try:
        # 验证任务所有权
        task = db.query(OCRTask).join(FileModel).filter(
            OCRTask.id == task_id,
            FileModel.user_id == current_user.id
        ).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取结果
        results = db.query(OCRResult).filter(
            OCRResult.task_id == task_id
        ).all()
        
        return {
            "task_id": task_id,
            "status": task.status,
            "engine": task.engine_type,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "results": [
                {
                    "page": result.page_number,
                    "text": result.extracted_text,
                    "confidence": result.confidence,
                    "bounding_boxes": result.bounding_boxes
                }
                for result in results
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取OCR结果失败: {e}")
        raise HTTPException(status_code=500, detail="获取结果失败")


# 获取任务状态API
@app.get("/api/ocr/status/{task_id}")
async def get_task_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """获取任务状态"""
    try:
        task = db.query(OCRTask).join(FileModel).filter(
            OCRTask.id == task_id,
            FileModel.user_id == current_user.id
        ).first()
        
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "task_id": task_id,
            "status": task.status,
            "progress": 100 if task.status == "completed" else 50 if task.status == "processing" else 0,
            "message": {
                "pending": "任务等待中",
                "processing": "正在处理中",
                "completed": "处理完成",
                "failed": "处理失败"
            }.get(task.status, "未知状态")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取状态失败")


# 用户信息API
@app.get("/api/user/profile")
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """获取用户信息"""
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "plan_type": current_user.plan_type,
        "api_quota": current_user.api_quota,
        "created_at": current_user.created_at
    }


# 异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误"}
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else 4
    )