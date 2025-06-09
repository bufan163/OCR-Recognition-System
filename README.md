# OCR识别系统

一个功能完整的OCR（光学字符识别）系统，支持免费和收费OCR引擎，提供Web API接口和完整的用户管理功能。

## 🚀 功能特性

### 核心功能
- **多引擎支持**: 集成免费引擎（Tesseract、PaddleOCR、EasyOCR）和收费引擎（百度OCR、腾讯云OCR、阿里云OCR、Azure OCR）
- **智能引擎选择**: 根据用户计划、文件类型和引擎可用性自动选择最佳OCR引擎
- **异步处理**: 使用Celery实现异步OCR任务处理，支持批量处理
- **多格式支持**: 支持PDF、PNG、JPG、JPEG、TIFF、BMP、WebP等格式
- **图像预处理**: 自动图像增强、降噪、倾斜校正等预处理功能

### 用户管理
- **多层级用户计划**: Free、Basic、Premium、Enterprise四种计划
- **配额管理**: 每日/每月使用限制，实时配额监控
- **JWT认证**: 安全的用户认证和授权机制
- **用户活动追踪**: 详细的用户操作日志和统计

### 管理功能
- **系统监控**: 实时系统状态、性能指标和使用统计
- **用户管理**: 管理员可管理用户账户、配额和权限
- **引擎配置**: 动态配置OCR引擎参数和优先级
- **数据清理**: 自动清理过期文件和任务记录

### 技术特性
- **高性能**: FastAPI框架，支持高并发请求
- **可扩展**: 微服务架构，支持水平扩展
- **容器化**: 完整的Docker部署方案
- **监控告警**: 集成Prometheus和Grafana监控
- **日志管理**: 结构化日志记录和轮转

## 🏗️ 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │   Mobile App    │    │   Third Party   │
│                 │    │                 │    │   Integration   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────┴─────────────┐
                    │      Nginx (Reverse       │
                    │       Proxy & Load        │
                    │        Balancer)          │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │     FastAPI Backend       │
                    │   (Authentication,        │
                    │    File Management,       │
                    │     OCR Orchestration)    │
                    └─────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
┌─────────┴─────────┐   ┌─────────┴─────────┐   ┌─────────┴─────────┐
│   PostgreSQL      │   │      Redis        │   │   Celery Workers  │
│   (Main Database) │   │   (Cache & Queue) │   │  (OCR Processing) │
└───────────────────┘   └───────────────────┘   └─────────┬─────────┘
                                                          │
                                            ┌─────────────┴─────────────┐
                                            │      OCR Engines          │
                                            │                           │
                                            │  ┌─────────────────────┐  │
                                            │  │   Free Engines      │  │
                                            │  │ • Tesseract        │  │
                                            │  │ • PaddleOCR        │  │
                                            │  │ • EasyOCR          │  │
                                            │  └─────────────────────┘  │
                                            │                           │
                                            │  ┌─────────────────────┐  │
                                            │  │   Paid Engines      │  │
                                            │  │ • 百度OCR          │  │
                                            │  │ • 腾讯云OCR        │  │
                                            │  │ • 阿里云OCR        │  │
                                            │  │ • Azure OCR        │  │
                                            │  └─────────────────────┘  │
                                            └───────────────────────────┘
```

## 📋 系统要求

### 最低要求
- **CPU**: 2核心
- **内存**: 4GB RAM
- **存储**: 20GB 可用空间
- **操作系统**: Linux (Ubuntu 20.04+), Windows 10+, macOS 10.15+

### 推荐配置
- **CPU**: 4核心或更多
- **内存**: 8GB RAM或更多
- **存储**: 50GB SSD
- **网络**: 稳定的互联网连接（用于收费OCR引擎）

## 🛠️ 安装部署

### 方式一：Docker部署（推荐）

1. **克隆项目**
```bash
git clone <repository-url>
cd OCR识别
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，配置数据库、Redis、OCR引擎等参数
```

3. **启动服务**
```bash
docker-compose up -d
```

4. **初始化数据库**
```bash
docker-compose exec backend python -c "from database import init_db; init_db()"
```

5. **创建管理员用户**
```bash
docker-compose exec backend python -c "
from services.auth_service import AuthService
from database import get_db
auth = AuthService()
db = next(get_db())
auth.register_user(db, 'admin', 'admin@example.com', 'your_password', is_admin=True)
"
```

### 方式二：本地开发部署

1. **安装Python依赖**
```bash
pip install -r requirements.txt
```

2. **安装系统依赖**

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng
sudo apt-get install libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1
sudo apt-get install poppler-utils
```

**Windows:**
- 下载并安装 [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
- 下载并安装 [Poppler](https://blog.alivate.com.au/poppler-windows/)

**macOS:**
```bash
brew install tesseract tesseract-lang
brew install poppler
```

3. **配置数据库**
```bash
# 安装并启动PostgreSQL
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# 创建数据库
sudo -u postgres createdb ocr_system
```

4. **配置Redis**
```bash
# 安装并启动Redis
sudo apt-get install redis-server
sudo systemctl start redis-server
```

5. **启动应用**
```bash
# 启动Celery Worker
celery -A celery_app worker --loglevel=info &

# 启动Celery Beat
celery -A celery_app beat --loglevel=info &

# 启动FastAPI应用
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## ⚙️ 配置说明

### 环境变量配置

主要配置项说明：

```bash
# 应用基础配置
APP_NAME="OCR识别系统"
APP_VERSION="1.0.0"
DEBUG=false
SECRET_KEY="your-secret-key-here"

# 数据库配置
DATABASE_URL="postgresql://username:password@localhost:5432/ocr_system"

# Redis配置
REDIS_URL="redis://localhost:6379/0"

# JWT配置
JWT_SECRET_KEY="your-jwt-secret-key"
JWT_ALGORITHM="HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# 文件存储配置
UPLOAD_DIR="./uploads"
MAX_FILE_SIZE=52428800  # 50MB
ALLOWED_EXTENSIONS=[".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]

# OCR引擎配置
DEFAULT_OCR_ENGINE="tesseract"

# 免费OCR引擎
TESSERACT_CMD="tesseract"
TESSERACT_DATA_PATH="/usr/share/tesseract-ocr/4.00/tessdata"

# 收费OCR引擎（需要申请API密钥）
BAIDU_OCR_APP_ID="your-baidu-app-id"
BAIDU_OCR_API_KEY="your-baidu-api-key"
BAIDU_OCR_SECRET_KEY="your-baidu-secret-key"

TENCENT_OCR_SECRET_ID="your-tencent-secret-id"
TENCENT_OCR_SECRET_KEY="your-tencent-secret-key"
TENCENT_OCR_REGION="ap-beijing"

ALIYUN_OCR_ACCESS_KEY_ID="your-aliyun-access-key-id"
ALIYUN_OCR_ACCESS_KEY_SECRET="your-aliyun-access-key-secret"
ALIYUN_OCR_REGION="cn-shanghai"

AZURE_OCR_SUBSCRIPTION_KEY="your-azure-subscription-key"
AZURE_OCR_ENDPOINT="https://your-resource-name.cognitiveservices.azure.com/"
```

### 用户计划配置

系统支持四种用户计划：

| 计划 | 每日限制 | 每月限制 | 支持引擎 | 功能特性 |
|------|----------|----------|----------|----------|
| Free | 10次 | 100次 | 免费引擎 | 基础OCR功能 |
| Basic | 100次 | 1000次 | 免费+百度OCR | 表格识别 |
| Premium | 500次 | 5000次 | 所有引擎 | 批量处理、优先队列 |
| Enterprise | 2000次 | 20000次 | 所有引擎 | 专属支持、自定义配额 |

## 📚 API文档

### 认证相关

#### 用户注册
```http
POST /auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123",
  "full_name": "测试用户"
}
```

#### 用户登录
```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=testuser&password=password123
```

### 文件管理

#### 上传文件
```http
POST /files/upload
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

file=@document.pdf
```

#### 获取文件列表
```http
GET /files/?page=1&size=20
Authorization: Bearer <access_token>
```

### OCR处理

#### 处理OCR任务
```http
POST /ocr/process
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "file_id": 123,
  "engine": "tesseract",
  "language": "chi_sim+eng",
  "preprocess": true,
  "extract_tables": false,
  "confidence_threshold": 0.5
}
```

#### 上传并处理
```http
POST /ocr/upload-and-process
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

file=@document.pdf&engine=tesseract&language=chi_sim+eng
```

#### 获取OCR结果
```http
GET /ocr/results/{task_id}
Authorization: Bearer <access_token>
```

#### 批量处理
```http
POST /ocr/process/batch
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "file_ids": [123, 124, 125],
  "engine": "paddleocr",
  "language": "chi_sim",
  "priority": 3
}
```

### 用户管理

#### 获取用户信息
```http
GET /users/profile
Authorization: Bearer <access_token>
```

#### 获取配额信息
```http
GET /users/quota
Authorization: Bearer <access_token>
```

#### 获取使用统计
```http
GET /users/stats
Authorization: Bearer <access_token>
```

### 管理员功能

#### 获取系统统计
```http
GET /admin/stats
Authorization: Bearer <admin_access_token>
```

#### 管理用户
```http
GET /admin/users?page=1&size=20
PUT /admin/users/{user_id}
DELETE /admin/users/{user_id}
Authorization: Bearer <admin_access_token>
```

## 🔧 OCR引擎配置

### 免费引擎

#### Tesseract OCR
- **优点**: 开源免费、支持多语言、本地处理
- **缺点**: 准确率相对较低、对图像质量要求高
- **适用场景**: 简单文档、开发测试

#### PaddleOCR
- **优点**: 中文识别效果好、支持表格识别
- **缺点**: 模型较大、首次加载慢
- **适用场景**: 中文文档、表格识别

#### EasyOCR
- **优点**: 易于使用、支持多语言
- **缺点**: 速度较慢、内存占用大
- **适用场景**: 多语言混合文档

### 收费引擎

#### 百度OCR
- **优点**: 识别准确率高、支持多种场景
- **费用**: 免费额度1000次/月，超出后按次计费
- **申请地址**: https://cloud.baidu.com/product/ocr

#### 腾讯云OCR
- **优点**: 识别速度快、支持实时识别
- **费用**: 免费额度1000次/月，超出后按次计费
- **申请地址**: https://cloud.tencent.com/product/ocr

#### 阿里云OCR
- **优点**: 企业级稳定性、丰富的API
- **费用**: 按调用次数计费
- **申请地址**: https://www.aliyun.com/product/ocr

#### Azure OCR
- **优点**: 国际化支持好、与Office集成
- **费用**: 免费额度5000次/月，超出后按次计费
- **申请地址**: https://azure.microsoft.com/services/cognitive-services/computer-vision/

## 📊 监控和日志

### Prometheus监控指标

系统提供以下监控指标：

- **应用指标**:
  - `ocr_requests_total`: OCR请求总数
  - `ocr_request_duration_seconds`: OCR请求处理时间
  - `ocr_engine_usage`: 各引擎使用次数
  - `user_quota_usage`: 用户配额使用情况

- **系统指标**:
  - `http_requests_total`: HTTP请求总数
  - `http_request_duration_seconds`: HTTP请求处理时间
  - `database_connections`: 数据库连接数
  - `redis_connections`: Redis连接数

### 日志管理

系统使用结构化日志，包含以下类型：

- **访问日志**: HTTP请求记录
- **应用日志**: 应用运行状态
- **性能日志**: 性能指标记录
- **用户活动日志**: 用户操作记录
- **安全日志**: 安全相关事件
- **系统事件日志**: 系统级别事件

日志文件位置：
```
logs/
├── access.log          # 访问日志
├── app.log            # 应用日志
├── performance.log    # 性能日志
├── user_activity.log  # 用户活动日志
├── security.log       # 安全日志
└── system.log         # 系统日志
```

## 🚀 性能优化

### 系统优化建议

1. **数据库优化**
   - 为常用查询字段添加索引
   - 定期清理过期数据
   - 使用连接池管理数据库连接

2. **缓存策略**
   - 使用Redis缓存频繁查询的数据
   - 缓存OCR结果避免重复处理
   - 实现用户会话缓存

3. **异步处理**
   - 使用Celery处理耗时的OCR任务
   - 实现任务优先级队列
   - 配置合适的Worker数量

4. **文件存储**
   - 使用对象存储服务（如AWS S3、阿里云OSS）
   - 实现文件压缩和去重
   - 定期清理临时文件

### 扩展部署

1. **水平扩展**
   - 部署多个API服务实例
   - 使用负载均衡器分发请求
   - 配置多个Celery Worker节点

2. **数据库扩展**
   - 配置数据库主从复制
   - 实现读写分离
   - 考虑分库分表策略

3. **缓存扩展**
   - 部署Redis集群
   - 实现缓存分片
   - 配置缓存高可用

## 🔒 安全考虑

### 安全措施

1. **认证和授权**
   - JWT令牌认证
   - 基于角色的访问控制
   - API密钥管理

2. **数据保护**
   - 密码哈希存储
   - 敏感数据加密
   - 文件访问权限控制

3. **网络安全**
   - HTTPS强制加密
   - CORS跨域保护
   - 请求频率限制

4. **输入验证**
   - 文件类型验证
   - 文件大小限制
   - SQL注入防护

### 安全配置建议

1. **生产环境配置**
   ```bash
   # 使用强密码
   SECRET_KEY="complex-random-string-here"
   JWT_SECRET_KEY="another-complex-random-string"
   
   # 禁用调试模式
   DEBUG=false
   
   # 配置HTTPS
   FORCE_HTTPS=true
   
   # 设置安全头
   SECURITY_HEADERS=true
   ```

2. **数据库安全**
   - 使用专用数据库用户
   - 限制数据库访问权限
   - 定期备份数据

3. **文件安全**
   - 限制上传文件类型
   - 扫描恶意文件
   - 隔离用户文件

## 🐛 故障排除

### 常见问题

1. **OCR引擎初始化失败**
   ```bash
   # 检查Tesseract安装
   tesseract --version
   
   # 检查语言包
   tesseract --list-langs
   
   # 检查Python包
   pip list | grep -E "(pytesseract|paddleocr|easyocr)"
   ```

2. **数据库连接失败**
   ```bash
   # 检查数据库服务
   sudo systemctl status postgresql
   
   # 测试连接
   psql -h localhost -U username -d ocr_system
   
   # 检查配置
   echo $DATABASE_URL
   ```

3. **Redis连接失败**
   ```bash
   # 检查Redis服务
   sudo systemctl status redis-server
   
   # 测试连接
   redis-cli ping
   
   # 检查配置
   echo $REDIS_URL
   ```

4. **Celery任务不执行**
   ```bash
   # 检查Celery Worker
   celery -A celery_app inspect active
   
   # 检查队列状态
   celery -A celery_app inspect stats
   
   # 重启Worker
   pkill -f "celery worker"
   celery -A celery_app worker --loglevel=info &
   ```

### 日志分析

1. **查看应用日志**
   ```bash
   tail -f logs/app.log
   ```

2. **查看错误日志**
   ```bash
   grep ERROR logs/app.log
   ```

3. **查看性能日志**
   ```bash
   tail -f logs/performance.log
   ```

## 📈 开发指南

### 项目结构

```
OCR识别/
├── main.py                 # FastAPI应用入口
├── config.py              # 配置文件
├── database.py            # 数据库连接
├── models.py              # 数据模型
├── celery_app.py          # Celery配置
├── requirements.txt       # Python依赖
├── Dockerfile            # Docker镜像
├── docker-compose.yml    # Docker编排
├── .env.example          # 环境变量模板
├── README.md             # 项目文档
│
├── api/                  # API路由
│   ├── __init__.py
│   ├── auth.py          # 认证相关API
│   ├── files.py         # 文件管理API
│   ├── ocr.py           # OCR处理API
│   ├── users.py         # 用户管理API
│   └── admin.py         # 管理员API
│
├── services/            # 业务逻辑层
│   ├── __init__.py
│   ├── auth_service.py  # 认证服务
│   ├── file_service.py  # 文件服务
│   └── ocr_service.py   # OCR服务
│
├── tasks/               # Celery任务
│   ├── __init__.py
│   ├── ocr_tasks.py     # OCR处理任务
│   ├── cleanup_tasks.py # 清理任务
│   └── stats_tasks.py   # 统计任务
│
├── utils/               # 工具函数
│   ├── __init__.py
│   ├── security.py      # 安全工具
│   └── logger.py        # 日志工具
│
├── uploads/             # 文件上传目录
├── logs/                # 日志目录
└── temp/                # 临时文件目录
```

### 添加新的OCR引擎

1. **在`services/ocr_service.py`中添加引擎实现**
   ```python
   async def process_with_new_engine(self, image_path: str, language: str) -> dict:
       """新引擎处理逻辑"""
       # 实现OCR处理逻辑
       pass
   ```

2. **更新引擎配置**
   ```python
   # 在config.py中添加引擎配置
   NEW_ENGINE_CONFIG = {
       "api_key": os.getenv("NEW_ENGINE_API_KEY"),
       "endpoint": os.getenv("NEW_ENGINE_ENDPOINT")
   }
   ```

3. **添加数据库记录**
   ```sql
   INSERT INTO ocr_engines (name, display_name, engine_type, is_enabled, priority, cost_per_page)
   VALUES ('new_engine', '新引擎', 'paid', true, 5, 0.01);
   ```

### 扩展API功能

1. **创建新的路由文件**
   ```python
   # api/new_feature.py
   from fastapi import APIRouter
   
   router = APIRouter(prefix="/new-feature", tags=["新功能"])
   
   @router.get("/")
   async def get_new_feature():
       return {"message": "新功能"}
   ```

2. **在main.py中注册路由**
   ```python
   from api import new_feature
   app.include_router(new_feature.router)
   ```

### 测试

1. **运行单元测试**
   ```bash
   pytest tests/
   ```

2. **API测试**
   ```bash
   # 使用httpie测试API
   http POST localhost:8000/auth/login username=admin password=password
   ```

3. **性能测试**
   ```bash
   # 使用ab进行压力测试
   ab -n 1000 -c 10 http://localhost:8000/
   ```

## 🤝 贡献指南

### 开发流程

1. **Fork项目**
2. **创建功能分支**
   ```bash
   git checkout -b feature/new-feature
   ```
3. **提交更改**
   ```bash
   git commit -m "Add new feature"
   ```
4. **推送分支**
   ```bash
   git push origin feature/new-feature
   ```
5. **创建Pull Request**

### 代码规范

1. **Python代码风格**
   - 遵循PEP 8规范
   - 使用类型注解
   - 添加文档字符串

2. **提交信息格式**
   ```
   type(scope): description
   
   [optional body]
   
   [optional footer]
   ```

3. **测试要求**
   - 新功能必须包含测试
   - 测试覆盖率不低于80%
   - 通过所有现有测试

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持和联系

- **问题反馈**: [GitHub Issues](https://github.com/your-repo/issues)
- **功能请求**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **邮件支持**: support@example.com
- **文档**: [在线文档](https://your-docs-site.com)

## 🙏 致谢

感谢以下开源项目的支持：

- [FastAPI](https://fastapi.tiangolo.com/) - 现代、快速的Web框架
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) - 开源OCR引擎
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - 百度开源OCR工具
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - 易用的OCR库
- [Celery](https://docs.celeryproject.org/) - 分布式任务队列
- [PostgreSQL](https://www.postgresql.org/) - 开源关系型数据库
- [Redis](https://redis.io/) - 内存数据结构存储

---

**注意**: 本项目仅供学习和研究使用。在生产环境中使用时，请确保遵守相关法律法规和服务条款。