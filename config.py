import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置类"""
    
    # 基础配置
    app_name: str = "OCR识别系统"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # 服务器配置
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # 数据库配置
    database_url: str = Field(
        default="sqlite:///./ocr_system.db",
        env="DATABASE_URL"
    )
    
    # Redis配置
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        env="REDIS_URL"
    )
    
    # JWT配置
    secret_key: str = Field(
        default="your-secret-key-change-in-production",
        env="SECRET_KEY"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # 文件存储配置
    upload_dir: str = Field(default="./uploads", env="UPLOAD_DIR")
    temp_dir: str = Field(default="./temp", env="TEMP_DIR")
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    allowed_extensions: list = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]
    
    # OCR引擎配置
    default_ocr_engine: str = Field(default="tesseract", env="DEFAULT_OCR_ENGINE")
    
    # 免费OCR引擎配置
    tesseract_enabled: bool = Field(default=True, env="TESSERACT_ENABLED")
    tesseract_cmd: Optional[str] = Field(default=None, env="TESSERACT_CMD")
    tesseract_path: Optional[str] = Field(default=None, env="TESSERACT_PATH")
    tesseract_lang: str = Field(default="chi_sim+eng", env="TESSERACT_LANG")
    
    paddleocr_enabled: bool = Field(default=True, env="PADDLEOCR_ENABLED")
    easyocr_enabled: bool = Field(default=True, env="EASYOCR_ENABLED")
    easyocr_langs: list = Field(default=["ch_sim", "en"], env="EASYOCR_LANGS")
    
    # PaddleOCR配置
    paddleocr_use_gpu: bool = Field(default=False, env="PADDLEOCR_USE_GPU")
    paddleocr_lang: str = Field(default="ch", env="PADDLEOCR_LANG")
    
    # EasyOCR配置
    easyocr_gpu: bool = Field(default=False, env="EASYOCR_GPU")
    easyocr_lang: list = Field(default=["ch_sim", "en"], env="EASYOCR_LANG")
    
    # 百度OCR配置
    baidu_ocr_enabled: bool = Field(default=False, env="BAIDU_OCR_ENABLED")
    baidu_app_id: Optional[str] = Field(default=None, env="BAIDU_APP_ID")
    baidu_api_key: Optional[str] = Field(default=None, env="BAIDU_API_KEY")
    baidu_secret_key: Optional[str] = Field(default=None, env="BAIDU_SECRET_KEY")
    
    # 腾讯云OCR配置
    tencent_ocr_enabled: bool = Field(default=False, env="TENCENT_OCR_ENABLED")
    tencent_secret_id: Optional[str] = Field(default=None, env="TENCENT_SECRET_ID")
    tencent_secret_key: Optional[str] = Field(default=None, env="TENCENT_SECRET_KEY")
    tencent_region: str = Field(default="ap-beijing", env="TENCENT_REGION")
    
    # 阿里云OCR配置
    ali_ocr_enabled: bool = Field(default=False, env="ALI_OCR_ENABLED")
    ali_access_key_id: Optional[str] = Field(default=None, env="ALI_ACCESS_KEY_ID")
    ali_access_key_secret: Optional[str] = Field(default=None, env="ALI_ACCESS_KEY_SECRET")
    ali_ocr_endpoint: str = Field(default="ocr.cn-shanghai.aliyuncs.com", env="ALI_OCR_ENDPOINT")
    
    # Azure OCR配置
    azure_ocr_enabled: bool = Field(default=False, env="AZURE_OCR_ENABLED")
    azure_subscription_key: Optional[str] = Field(default=None, env="AZURE_SUBSCRIPTION_KEY")
    azure_endpoint: Optional[str] = Field(default=None, env="AZURE_ENDPOINT")
    
    # Celery配置
    celery_broker_url: str = Field(
        default="redis://localhost:6379/1",
        env="CELERY_BROKER_URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/2",
        env="CELERY_RESULT_BACKEND"
    )
    
    # 日志配置
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="./logs/app.log", env="LOG_FILE")
    
    # 限流配置
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")
    
    # 用户配额配置
    free_user_daily_quota: int = Field(default=100, env="FREE_USER_DAILY_QUOTA")
    premium_user_daily_quota: int = Field(default=10000, env="PREMIUM_USER_DAILY_QUOTA")
    
    # 图像预处理配置
    enable_image_preprocessing: bool = Field(default=True, env="ENABLE_IMAGE_PREPROCESSING")
    image_dpi: int = Field(default=300, env="IMAGE_DPI")
    
    # 监控配置
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }


# 创建全局配置实例
settings = Settings()


# OCR引擎优先级配置
OCR_ENGINE_PRIORITY = {
    "free": ["paddleocr", "tesseract", "easyocr"],
    "premium": ["baidu_ocr", "tencent_ocr", "aliyun_ocr", "azure_ocr"],
    "auto": ["baidu_ocr", "paddleocr", "tesseract"]
}

# 支持的文件类型
SUPPORTED_FILE_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".webp": "image/webp"
}

# OCR引擎成本配置（每次调用成本，单位：元）
OCR_ENGINE_COSTS = {
    "tesseract": 0.0,
    "paddleocr": 0.0,
    "easyocr": 0.0,
    "baidu_ocr": 0.004,
    "baidu_ocr_accurate": 0.008,
    "tencent_ocr": 0.006,
    "aliyun_ocr": 0.01,
    "azure_ocr": 0.01
}

# 数据库连接池配置
DATABASE_CONFIG = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600
}

# 缓存配置
CACHE_CONFIG = {
    "default_timeout": 3600,  # 1小时
    "ocr_result_timeout": 86400,  # 24小时
    "user_quota_timeout": 86400  # 24小时
}