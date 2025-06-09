import os
import io
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from PIL import Image
import cv2
import numpy as np
from pdf2image import convert_from_path, convert_from_bytes
import fitz  # PyMuPDF

# 免费OCR引擎
import pytesseract
try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

try:
    import easyocr
except ImportError:
    easyocr = None

# 收费OCR引擎
try:
    from aip import AipOcr  # 百度OCR
except ImportError:
    AipOcr = None

try:
    from tencentcloud.common import credential
    from tencentcloud.ocr.v20181119 import ocr_client, models
except ImportError:
    credential = None
    ocr_client = None
    models = None

try:
    from alibabacloud_ocr_api20210707.client import Client as AliOcrClient
    from alibabacloud_tea_openapi import models as open_api_models
except ImportError:
    AliOcrClient = None
    open_api_models = None

try:
    from azure.cognitiveservices.vision.computervision import ComputerVisionClient
    from msrest.authentication import CognitiveServicesCredentials
except ImportError:
    ComputerVisionClient = None
    CognitiveServicesCredentials = None

from models import OCRTask, OCRResult, File, APIUsage
from utils.logger import setup_logger, log_performance
from config import settings, OCR_ENGINE_PRIORITY, OCR_ENGINE_COSTS


class OCRService:
    """OCR服务类"""
    
    def __init__(self):
        self.logger = setup_logger("ocr_service")
        self.temp_dir = Path(settings.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化OCR引擎
        self._init_engines()
    
    def _init_engines(self):
        """初始化OCR引擎"""
        self.engines = {}
        
        # 初始化Tesseract
        if settings.tesseract_enabled:
            try:
                pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path
                self.engines['tesseract'] = True
                self.logger.info("Tesseract OCR 初始化成功")
            except Exception as e:
                self.logger.error(f"Tesseract OCR 初始化失败: {e}")
        
        # 初始化PaddleOCR
        if settings.paddleocr_enabled and PaddleOCR:
            try:
                self.paddle_ocr = PaddleOCR(
                    use_angle_cls=True,
                    lang=settings.paddleocr_lang,
                    use_gpu=settings.paddleocr_use_gpu
                )
                self.engines['paddleocr'] = True
                self.logger.info("PaddleOCR 初始化成功")
            except Exception as e:
                self.logger.error(f"PaddleOCR 初始化失败: {e}")
        
        # 初始化EasyOCR
        if settings.easyocr_enabled and easyocr:
            try:
                self.easy_reader = easyocr.Reader(
                    settings.easyocr_langs,
                    gpu=settings.easyocr_use_gpu
                )
                self.engines['easyocr'] = True
                self.logger.info("EasyOCR 初始化成功")
            except Exception as e:
                self.logger.error(f"EasyOCR 初始化失败: {e}")
        
        # 初始化百度OCR
        if settings.baidu_ocr_enabled and AipOcr:
            try:
                self.baidu_client = AipOcr(
                    settings.baidu_app_id,
                    settings.baidu_api_key,
                    settings.baidu_secret_key
                )
                self.engines['baidu'] = True
                self.logger.info("百度OCR 初始化成功")
            except Exception as e:
                self.logger.error(f"百度OCR 初始化失败: {e}")
        
        # 初始化腾讯云OCR
        if settings.tencent_ocr_enabled and credential:
            try:
                cred = credential.Credential(
                    settings.tencent_secret_id,
                    settings.tencent_secret_key
                )
                self.tencent_client = ocr_client.OcrClient(cred, settings.tencent_region)
                self.engines['tencent'] = True
                self.logger.info("腾讯云OCR 初始化成功")
            except Exception as e:
                self.logger.error(f"腾讯云OCR 初始化失败: {e}")
        
        # 初始化阿里云OCR
        if settings.ali_ocr_enabled and AliOcrClient:
            try:
                config = open_api_models.Config(
                    access_key_id=settings.ali_access_key_id,
                    access_key_secret=settings.ali_access_key_secret
                )
                config.endpoint = settings.ali_ocr_endpoint
                self.ali_client = AliOcrClient(config)
                self.engines['ali'] = True
                self.logger.info("阿里云OCR 初始化成功")
            except Exception as e:
                self.logger.error(f"阿里云OCR 初始化失败: {e}")
        
        # 初始化Azure OCR
        if settings.azure_ocr_enabled and ComputerVisionClient:
            try:
                self.azure_client = ComputerVisionClient(
                    settings.azure_ocr_endpoint,
                    CognitiveServicesCredentials(settings.azure_ocr_key)
                )
                self.engines['azure'] = True
                self.logger.info("Azure OCR 初始化成功")
            except Exception as e:
                self.logger.error(f"Azure OCR 初始化失败: {e}")
        
        self.logger.info(f"已初始化OCR引擎: {list(self.engines.keys())}")
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """图像预处理"""
        try:
            # 转换为OpenCV格式
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            
            # 灰度化
            if settings.image_preprocessing.get('grayscale', True):
                cv_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            
            # 降噪
            if settings.image_preprocessing.get('denoise', True):
                cv_image = cv2.fastNlMeansDenoising(cv_image)
            
            # 二值化
            if settings.image_preprocessing.get('binarize', True):
                _, cv_image = cv2.threshold(cv_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 形态学操作
            if settings.image_preprocessing.get('morphology', False):
                kernel = np.ones((2, 2), np.uint8)
                cv_image = cv2.morphologyEx(cv_image, cv2.MORPH_CLOSE, kernel)
            
            # 转换回PIL格式
            if len(cv_image.shape) == 2:  # 灰度图
                processed_image = Image.fromarray(cv_image, mode='L')
            else:
                processed_image = Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
            
            return processed_image
            
        except Exception as e:
            self.logger.warning(f"图像预处理失败，使用原图: {e}")
            return image
    
    def _extract_images_from_pdf(self, pdf_path: str) -> List[Image.Image]:
        """从PDF提取图像"""
        images = []
        
        try:
            # 方法1: 使用PyMuPDF提取
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # 提取页面中的图像
                image_list = page.get_images()
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("png")
                        image = Image.open(io.BytesIO(img_data))
                        images.append(image)
                    pix = None
                
                # 如果没有提取到图像，将整页转换为图像
                if not image_list:
                    mat = fitz.Matrix(2, 2)  # 提高分辨率
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    image = Image.open(io.BytesIO(img_data))
                    images.append(image)
                    pix = None
            
            doc.close()
            
        except Exception as e:
            self.logger.warning(f"PyMuPDF提取失败，尝试pdf2image: {e}")
            
            try:
                # 方法2: 使用pdf2image
                pages = convert_from_path(
                    pdf_path,
                    dpi=settings.pdf_dpi,
                    first_page=1,
                    last_page=settings.max_pdf_pages
                )
                images.extend(pages)
                
            except Exception as e2:
                self.logger.error(f"pdf2image提取也失败: {e2}")
                raise ValueError("PDF图像提取失败")
        
        return images
    
    async def _ocr_tesseract(self, image: Image.Image) -> Dict[str, Any]:
        """Tesseract OCR识别"""
        try:
            # 预处理图像
            processed_image = self._preprocess_image(image)
            
            # OCR识别
            text = pytesseract.image_to_string(
                processed_image,
                lang=settings.tesseract_lang,
                config=settings.tesseract_config
            )
            
            # 获取详细信息
            data = pytesseract.image_to_data(
                processed_image,
                lang=settings.tesseract_lang,
                output_type=pytesseract.Output.DICT
            )
            
            # 提取文本块信息
            blocks = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 0:
                    blocks.append({
                        'text': data['text'][i],
                        'confidence': float(data['conf'][i]) / 100,
                        'bbox': [
                            data['left'][i],
                            data['top'][i],
                            data['left'][i] + data['width'][i],
                            data['top'][i] + data['height'][i]
                        ]
                    })
            
            return {
                'text': text.strip(),
                'confidence': sum(float(conf) for conf in data['conf'] if int(conf) > 0) / len([conf for conf in data['conf'] if int(conf) > 0]) / 100 if any(int(conf) > 0 for conf in data['conf']) else 0,
                'blocks': blocks,
                'engine': 'tesseract'
            }
            
        except Exception as e:
            self.logger.error(f"Tesseract OCR失败: {e}")
            raise
    
    async def _ocr_paddleocr(self, image: Image.Image) -> Dict[str, Any]:
        """PaddleOCR识别"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # OCR识别
            result = self.paddle_ocr.ocr(img_array, cls=True)
            
            if not result or not result[0]:
                return {
                    'text': '',
                    'confidence': 0,
                    'blocks': [],
                    'engine': 'paddleocr'
                }
            
            # 解析结果
            text_lines = []
            blocks = []
            total_confidence = 0
            
            for line in result[0]:
                if line:
                    bbox, (text, confidence) = line
                    text_lines.append(text)
                    total_confidence += confidence
                    
                    blocks.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': [int(coord) for point in bbox for coord in point]
                    })
            
            avg_confidence = total_confidence / len(result[0]) if result[0] else 0
            
            return {
                'text': '\n'.join(text_lines),
                'confidence': avg_confidence,
                'blocks': blocks,
                'engine': 'paddleocr'
            }
            
        except Exception as e:
            self.logger.error(f"PaddleOCR失败: {e}")
            raise
    
    async def _ocr_easyocr(self, image: Image.Image) -> Dict[str, Any]:
        """EasyOCR识别"""
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # OCR识别
            result = self.easy_reader.readtext(img_array)
            
            if not result:
                return {
                    'text': '',
                    'confidence': 0,
                    'blocks': [],
                    'engine': 'easyocr'
                }
            
            # 解析结果
            text_lines = []
            blocks = []
            total_confidence = 0
            
            for bbox, text, confidence in result:
                text_lines.append(text)
                total_confidence += confidence
                
                # 转换bbox格式
                x_coords = [point[0] for point in bbox]
                y_coords = [point[1] for point in bbox]
                
                blocks.append({
                    'text': text,
                    'confidence': confidence,
                    'bbox': [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]
                })
            
            avg_confidence = total_confidence / len(result) if result else 0
            
            return {
                'text': '\n'.join(text_lines),
                'confidence': avg_confidence,
                'blocks': blocks,
                'engine': 'easyocr'
            }
            
        except Exception as e:
            self.logger.error(f"EasyOCR失败: {e}")
            raise
    
    async def _ocr_baidu(self, image: Image.Image) -> Dict[str, Any]:
        """百度OCR识别"""
        try:
            # 转换为字节流
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_data = img_byte_arr.getvalue()
            
            # 调用百度OCR API
            result = self.baidu_client.basicGeneral(img_data)
            
            if 'error_code' in result:
                raise Exception(f"百度OCR API错误: {result['error_msg']}")
            
            if 'words_result' not in result:
                return {
                    'text': '',
                    'confidence': 0,
                    'blocks': [],
                    'engine': 'baidu'
                }
            
            # 解析结果
            text_lines = []
            blocks = []
            
            for item in result['words_result']:
                text = item['words']
                text_lines.append(text)
                
                # 百度OCR基础版本没有位置信息
                blocks.append({
                    'text': text,
                    'confidence': 0.9,  # 默认置信度
                    'bbox': [0, 0, 0, 0]  # 无位置信息
                })
            
            return {
                'text': '\n'.join(text_lines),
                'confidence': 0.9,  # 百度OCR基础版本没有置信度信息
                'blocks': blocks,
                'engine': 'baidu'
            }
            
        except Exception as e:
            self.logger.error(f"百度OCR失败: {e}")
            raise
    
    async def process_file(self, db: Session, file_id: int, user_id: int, engine_preference: Optional[str] = None) -> OCRTask:
        """处理文件OCR任务"""
        try:
            # 获取文件信息
            file_record = db.query(File).filter(
                File.id == file_id,
                File.user_id == user_id
            ).first()
            
            if not file_record:
                raise ValueError("文件不存在")
            
            # 创建OCR任务
            task = OCRTask(
                user_id=user_id,
                file_id=file_id,
                status="processing",
                engine_used="",
                total_pages=0,
                processed_pages=0
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            
            # 异步处理
            asyncio.create_task(self._process_file_async(db, task.id, file_record, engine_preference))
            
            return task
            
        except Exception as e:
            db.rollback()
            self.logger.error(f"创建OCR任务失败: {e}")
            raise
    
    async def _process_file_async(self, db: Session, task_id: int, file_record: File, engine_preference: Optional[str] = None):
        """异步处理文件OCR"""
        start_time = datetime.now()
        
        try:
            # 获取任务
            task = db.query(OCRTask).filter(OCRTask.id == task_id).first()
            if not task:
                return
            
            # 提取图像
            if file_record.file_type == 'pdf':
                images = self._extract_images_from_pdf(file_record.file_path)
            else:
                image = Image.open(file_record.file_path)
                images = [image]
            
            task.total_pages = len(images)
            db.commit()
            
            # 选择OCR引擎
            engine = self._select_engine(engine_preference)
            task.engine_used = engine
            db.commit()
            
            # 处理每个图像
            all_results = []
            for i, image in enumerate(images):
                try:
                    # 执行OCR
                    result = await self._execute_ocr(engine, image)
                    
                    # 保存结果
                    ocr_result = OCRResult(
                        task_id=task_id,
                        page_number=i + 1,
                        text_content=result['text'],
                        confidence_score=result['confidence'],
                        bounding_boxes=result['blocks'],
                        engine_used=engine
                    )
                    
                    db.add(ocr_result)
                    all_results.append(result)
                    
                    # 更新进度
                    task.processed_pages = i + 1
                    db.commit()
                    
                except Exception as e:
                    self.logger.error(f"处理第{i+1}页失败: {e}")
                    continue
            
            # 更新任务状态
            task.status = "completed"
            task.completed_at = datetime.now()
            
            # 计算总体置信度
            if all_results:
                avg_confidence = sum(r['confidence'] for r in all_results) / len(all_results)
                task.confidence_score = avg_confidence
            
            db.commit()
            
            # 记录API使用
            self._record_api_usage(db, task.user_id, engine, len(images))
            
            # 记录性能日志
            processing_time = (datetime.now() - start_time).total_seconds()
            log_performance(
                operation="ocr_processing",
                duration=processing_time,
                details={
                    "task_id": task_id,
                    "engine": engine,
                    "pages": len(images),
                    "file_type": file_record.file_type
                }
            )
            
            self.logger.info(f"OCR任务完成: {task_id}, 引擎: {engine}, 页数: {len(images)}, 耗时: {processing_time:.2f}s")
            
        except Exception as e:
            # 更新任务状态为失败
            task = db.query(OCRTask).filter(OCRTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                db.commit()
            
            self.logger.error(f"OCR任务失败: {task_id} - {e}")
    
    def _select_engine(self, preference: Optional[str] = None) -> str:
        """选择OCR引擎"""
        # 如果指定了偏好引擎且可用
        if preference and preference in self.engines:
            return preference
        
        # 按优先级选择可用引擎
        for engine in OCR_ENGINE_PRIORITY:
            if engine in self.engines:
                return engine
        
        # 如果没有可用引擎
        raise ValueError("没有可用的OCR引擎")
    
    async def _execute_ocr(self, engine: str, image: Image.Image) -> Dict[str, Any]:
        """执行OCR识别"""
        if engine == 'tesseract':
            return await self._ocr_tesseract(image)
        elif engine == 'paddleocr':
            return await self._ocr_paddleocr(image)
        elif engine == 'easyocr':
            return await self._ocr_easyocr(image)
        elif engine == 'baidu':
            return await self._ocr_baidu(image)
        # 可以继续添加其他引擎
        else:
            raise ValueError(f"不支持的OCR引擎: {engine}")
    
    def _record_api_usage(self, db: Session, user_id: int, engine: str, pages: int):
        """记录API使用情况"""
        try:
            cost_per_page = OCR_ENGINE_COSTS.get(engine, 0)
            total_cost = cost_per_page * pages
            
            usage = APIUsage(
                user_id=user_id,
                engine=engine,
                pages_processed=pages,
                cost=total_cost
            )
            
            db.add(usage)
            db.commit()
            
        except Exception as e:
            self.logger.error(f"记录API使用失败: {e}")
    
    def get_task_status(self, db: Session, task_id: int, user_id: int = None) -> Optional[OCRTask]:
        """获取任务状态"""
        query = db.query(OCRTask).filter(OCRTask.id == task_id)
        if user_id:
            query = query.filter(OCRTask.user_id == user_id)
        return query.first()
    
    def get_task_results(self, db: Session, task_id: int, user_id: int = None) -> List[OCRResult]:
        """获取任务结果"""
        task = self.get_task_status(db, task_id, user_id)
        if not task:
            return []
        
        return db.query(OCRResult).filter(
            OCRResult.task_id == task_id
        ).order_by(OCRResult.page_number).all()
    
    def get_available_engines(self) -> List[Dict[str, Any]]:
        """获取可用的OCR引擎列表"""
        engines_info = []
        
        for engine_name in self.engines:
            engine_info = {
                'name': engine_name,
                'type': 'free' if engine_name in ['tesseract', 'paddleocr', 'easyocr'] else 'paid',
                'cost_per_page': OCR_ENGINE_COSTS.get(engine_name, 0),
                'available': True
            }
            engines_info.append(engine_info)
        
        return engines_info