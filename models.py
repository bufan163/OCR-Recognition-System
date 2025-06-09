from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, DECIMAL, JSON, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    """用户模型"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    plan_type = Column(String(20), default="free")  # free, premium, enterprise
    api_quota = Column(Integer, default=1000)  # 每日API配额
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)  # 是否为管理员
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    files = relationship("File", back_populates="user", cascade="all, delete-orphan")
    api_usage = relationship("APIUsage", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', plan='{self.plan_type}')>"


class File(Base):
    """文件模型"""
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, image
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), index=True)  # MD5哈希，用于去重
    status = Column(String(20), default="uploaded")  # uploaded, processing, completed, failed
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    
    # 关系
    user = relationship("User", back_populates="files")
    ocr_tasks = relationship("OCRTask", back_populates="file", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<File(id={self.id}, filename='{self.filename}', status='{self.status}')>"


class OCRTask(Base):
    """OCR任务模型"""
    __tablename__ = "ocr_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    engine_type = Column(String(50), nullable=False)  # tesseract, paddleocr, baidu_ocr等
    language = Column(String(50), default="chi_sim+eng")
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    priority = Column(Integer, default=0)  # 任务优先级，数字越大优先级越高
    progress = Column(Integer, default=0)  # 进度百分比
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True))
    processing_time = Column(Float)  # 处理时间（秒）
    error_message = Column(Text)
    cost = Column(DECIMAL(10, 4), default=0.0000)  # 处理成本
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 任务配置
    options = Column(JSON)  # 存储任务配置选项
    
    # 关系
    file = relationship("File", back_populates="ocr_tasks")
    results = relationship("OCRResult", back_populates="task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<OCRTask(id={self.id}, engine='{self.engine_type}', status='{self.status}')>"


class OCRResult(Base):
    """OCR结果模型"""
    __tablename__ = "ocr_results"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("ocr_tasks.id"), nullable=False, index=True)
    page_number = Column(Integer, default=1)  # 页码
    extracted_text = Column(Text)  # 提取的文本
    confidence = Column(Float)  # 识别置信度
    word_count = Column(Integer)  # 字数统计
    
    # 位置信息
    bounding_boxes = Column(JSON)  # 文字边界框信息
    
    # 元数据
    language_detected = Column(String(50))  # 检测到的语言
    processing_time = Column(Float)  # 单页处理时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    task = relationship("OCRTask", back_populates="results")
    
    def __repr__(self):
        return f"<OCRResult(id={self.id}, page={self.page_number}, confidence={self.confidence})>"


class APIUsage(Base):
    """API使用记录模型"""
    __tablename__ = "api_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)  # API端点
    method = Column(String(10), nullable=False)  # HTTP方法
    status_code = Column(Integer, nullable=False)  # 响应状态码
    response_time = Column(Integer)  # 响应时间（毫秒）
    request_size = Column(BigInteger)  # 请求大小（字节）
    response_size = Column(BigInteger)  # 响应大小（字节）
    cost = Column(DECIMAL(10, 4), default=0.0000)  # 调用成本
    ip_address = Column(String(45))  # 客户端IP
    user_agent = Column(String(500))  # 用户代理
    request_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    
    # 关系
    user = relationship("User", back_populates="api_usage")
    
    def __repr__(self):
        return f"<APIUsage(id={self.id}, endpoint='{self.endpoint}', status={self.status_code})>"


class UserQuota(Base):
    """用户配额模型"""
    __tablename__ = "user_quotas"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    quota_type = Column(String(20), nullable=False)  # daily, monthly
    quota_limit = Column(Integer, nullable=False)  # 配额限制
    quota_used = Column(Integer, default=0)  # 已使用配额
    reset_time = Column(DateTime(timezone=True), nullable=False)  # 配额重置时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<UserQuota(user_id={self.user_id}, type='{self.quota_type}', used={self.quota_used}/{self.quota_limit})>"


class SystemConfig(Base):
    """系统配置模型"""
    __tablename__ = "system_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text)
    config_type = Column(String(20), default="string")  # string, integer, float, boolean, json
    description = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemConfig(key='{self.config_key}', value='{self.config_value}')>"


class OCREngine(Base):
    """OCR引擎配置模型"""
    __tablename__ = "ocr_engines"
    
    id = Column(Integer, primary_key=True, index=True)
    engine_name = Column(String(50), unique=True, nullable=False, index=True)
    engine_type = Column(String(20), nullable=False)  # free, premium
    is_enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # 优先级
    cost_per_call = Column(DECIMAL(10, 4), default=0.0000)  # 每次调用成本
    max_file_size = Column(BigInteger)  # 最大文件大小限制
    supported_formats = Column(JSON)  # 支持的文件格式
    api_config = Column(JSON)  # API配置信息
    rate_limit = Column(Integer)  # 速率限制（每分钟调用次数）
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<OCREngine(name='{self.engine_name}', type='{self.engine_type}', enabled={self.is_enabled})>"