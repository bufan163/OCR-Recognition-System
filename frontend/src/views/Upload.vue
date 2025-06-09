<template>
  <div class="upload-page">
    <div class="upload-header">
      <h1>文件上传</h1>
      <p>支持上传图片和PDF文件进行OCR识别</p>
    </div>
    
    <div class="upload-container">
      <!-- 上传区域 -->
      <el-card class="upload-card" shadow="hover">
        <div class="upload-area">
          <el-upload
            ref="uploadRef"
            class="upload-dragger"
            drag
            :multiple="true"
            :auto-upload="false"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :accept="acceptedTypes"
            :before-upload="beforeUpload"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 jpg/png/gif/bmp/pdf 格式，单个文件不超过 10MB
              </div>
            </template>
          </el-upload>
        </div>
      </el-card>
      
      <!-- 文件列表 -->
      <el-card v-if="fileList.length > 0" class="file-list-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>文件列表 ({{ fileList.length }})</span>
            <el-button type="danger" size="small" @click="clearFiles">
              清空列表
            </el-button>
          </div>
        </template>
        
        <div class="file-list">
          <div 
            v-for="(file, index) in fileList" 
            :key="file.uid" 
            class="file-item"
          >
            <div class="file-info">
              <div class="file-preview">
                <img 
                  v-if="file.preview && isImageFile(file.name)"
                  :src="file.preview"
                  class="preview-image"
                  @error="handleImageError"
                />
                <el-icon v-else class="file-icon" size="32">
                  <Picture v-if="isImageFile(file.name)" />
                  <Document v-else />
                </el-icon>
              </div>
              
              <div class="file-details">
                <div class="file-name">{{ file.name }}</div>
                <div class="file-meta">
                  <span class="file-size">{{ formatFileSize(file.size) }}</span>
                  <span class="file-type">{{ getFileExtension(file.name).toUpperCase() }}</span>
                </div>
                
                <!-- 上传进度 -->
                <div v-if="file.uploading" class="upload-progress">
                  <el-progress 
                    :percentage="file.progress || 0" 
                    :status="file.status === 'error' ? 'exception' : undefined"
                    size="small"
                  />
                  <span class="progress-text">
                    {{ file.status === 'error' ? '上传失败' : '上传中...' }}
                  </span>
                </div>
                
                <!-- 识别结果状态 -->
                <div v-if="file.result" class="result-status">
                  <el-tag 
                    :type="getStatusType(file.result.status)"
                    size="small"
                  >
                    {{ getStatusText(file.result.status) }}
                  </el-tag>
                  <el-button 
                    v-if="file.result.status === 'completed'"
                    type="primary" 
                    link 
                    size="small"
                    @click="viewResult(file.result.id)"
                  >
                    查看结果
                  </el-button>
                </div>
              </div>
            </div>
            
            <div class="file-actions">
              <el-button 
                type="danger" 
                size="small" 
                circle
                @click="removeFile(index)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
      
      <!-- 识别设置 -->
      <el-card v-if="fileList.length > 0" class="settings-card" shadow="hover">
        <template #header>
          <span>识别设置</span>
        </template>
        
        <el-form :model="ocrSettings" label-width="100px">
          <el-form-item label="识别引擎">
            <el-select v-model="ocrSettings.engine" placeholder="选择识别引擎">
              <el-option 
                v-for="engine in availableEngines" 
                :key="engine.value" 
                :label="engine.label" 
                :value="engine.value"
              />
            </el-select>
          </el-form-item>
          
          <el-form-item label="识别语言">
            <el-select v-model="ocrSettings.language" placeholder="选择识别语言">
              <el-option label="中文" value="zh" />
              <el-option label="英文" value="en" />
              <el-option label="中英文混合" value="zh-en" />
            </el-select>
          </el-form-item>
          
          <el-form-item label="图像预处理">
            <el-checkbox-group v-model="ocrSettings.preprocessing">
              <el-checkbox label="auto_rotate">自动旋转</el-checkbox>
              <el-checkbox label="denoise">降噪处理</el-checkbox>
              <el-checkbox label="enhance">图像增强</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
      </el-card>
      
      <!-- 操作按钮 -->
      <div v-if="fileList.length > 0" class="action-buttons">
        <el-button 
          type="primary" 
          size="large"
          :loading="uploading"
          :disabled="fileList.length === 0"
          @click="startUpload"
        >
          {{ uploading ? '识别中...' : '开始识别' }}
        </el-button>
        
        <el-button 
          size="large"
          @click="clearFiles"
        >
          清空文件
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { UploadFilled, Picture, Document, Delete } from '@element-plus/icons-vue'
import { useOcrStore } from '@/stores/ocr'
import { formatFileSize, getFileExtension, isImageFile, getFilePreviewUrl, revokeFilePreviewUrl } from '@/utils'

const router = useRouter()
const ocrStore = useOcrStore()

const uploadRef = ref()
const fileList = ref([])
const uploading = ref(false)
const availableEngines = ref([
  { label: 'Tesseract', value: 'tesseract' },
  { label: 'PaddleOCR', value: 'paddleocr' },
  { label: 'EasyOCR', value: 'easyocr' },
  { label: '百度OCR', value: 'baidu' },
  { label: '腾讯OCR', value: 'tencent' }
])

const ocrSettings = reactive({
  engine: 'paddleocr',
  language: 'zh-en',
  preprocessing: ['auto_rotate']
})

const acceptedTypes = '.jpg,.jpeg,.png,.gif,.bmp,.pdf'
const maxFileSize = 10 * 1024 * 1024 // 10MB

const beforeUpload = (file) => {
  const isValidType = /\.(jpg|jpeg|png|gif|bmp|pdf)$/i.test(file.name)
  const isValidSize = file.size <= maxFileSize
  
  if (!isValidType) {
    ElMessage.error('只支持 jpg/png/gif/bmp/pdf 格式的文件')
    return false
  }
  
  if (!isValidSize) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  
  return true
}

const handleFileChange = (file, files) => {
  if (!beforeUpload(file.raw)) {
    return
  }
  
  // 生成预览
  if (isImageFile(file.name)) {
    file.preview = getFilePreviewUrl(file.raw)
  }
  
  // 添加到文件列表
  const fileItem = {
    uid: file.uid,
    name: file.name,
    size: file.size,
    raw: file.raw,
    preview: file.preview,
    uploading: false,
    progress: 0,
    status: 'ready',
    result: null
  }
  
  fileList.value.push(fileItem)
}

const handleFileRemove = (file) => {
  const index = fileList.value.findIndex(item => item.uid === file.uid)
  if (index > -1) {
    removeFile(index)
  }
}

const removeFile = (index) => {
  const file = fileList.value[index]
  if (file.preview) {
    revokeFilePreviewUrl(file.preview)
  }
  fileList.value.splice(index, 1)
}

const clearFiles = () => {
  fileList.value.forEach(file => {
    if (file.preview) {
      revokeFilePreviewUrl(file.preview)
    }
  })
  fileList.value = []
  uploadRef.value?.clearFiles()
}

const handleImageError = (event) => {
  event.target.style.display = 'none'
}

const getStatusType = (status) => {
  const statusMap = {
    'completed': 'success',
    'processing': 'warning',
    'failed': 'danger',
    'pending': 'info'
  }
  return statusMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusMap = {
    'completed': '识别完成',
    'processing': '识别中',
    'failed': '识别失败',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

const viewResult = (id) => {
  router.push(`/results/${id}`)
}

const startUpload = async () => {
  if (fileList.value.length === 0) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  uploading.value = true
  
  try {
    for (const file of fileList.value) {
      if (file.result) continue // 跳过已处理的文件
      
      file.uploading = true
      file.progress = 0
      file.status = 'uploading'
      
      try {
        const result = await ocrStore.uploadFile(file.raw, {
          engine: ocrSettings.engine,
          language: ocrSettings.language,
          preprocessing: ocrSettings.preprocessing.join(',')
        })
        
        file.uploading = false
        file.progress = 100
        file.status = 'success'
        file.result = result
        
        ElMessage.success(`${file.name} 上传成功`)
        
      } catch (error) {
        file.uploading = false
        file.status = 'error'
        ElMessage.error(`${file.name} 上传失败: ${error.message}`)
      }
    }
    
    ElMessage.success('所有文件处理完成')
    
  } catch (error) {
    ElMessage.error('批量上传失败')
  } finally {
    uploading.value = false
  }
}

// 清理预览URL
onUnmounted(() => {
  fileList.value.forEach(file => {
    if (file.preview) {
      revokeFilePreviewUrl(file.preview)
    }
  })
})

// 加载可用引擎
onMounted(async () => {
  try {
    const engines = await ocrStore.getEngines()
    if (engines && engines.length > 0) {
      availableEngines.value = engines.map(engine => ({
        label: engine.name || engine.value,
        value: engine.value
      }))
    }
  } catch (error) {
    console.error('加载引擎列表失败:', error)
  }
})
</script>

<style scoped>
.upload-page {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.upload-header {
  margin-bottom: 32px;
  text-align: center;
}

.upload-header h1 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 32px;
  font-weight: 600;
}

.upload-header p {
  margin: 0;
  color: #909399;
  font-size: 16px;
}

.upload-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.upload-card {
  border: 2px dashed #dcdfe6;
  transition: border-color 0.3s;
}

.upload-card:hover {
  border-color: #409eff;
}

.upload-area {
  padding: 20px;
}

.upload-dragger {
  width: 100%;
}

:deep(.el-upload-dragger) {
  width: 100%;
  height: 200px;
  border: none;
  border-radius: 8px;
  background: #fafafa;
}

:deep(.el-upload-dragger:hover) {
  background: #f5f7fa;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.file-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fafafa;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.file-preview {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #f5f7fa;
  overflow: hidden;
}

.preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 8px;
}

.file-icon {
  color: #909399;
}

.file-details {
  flex: 1;
}

.file-name {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  word-break: break-all;
}

.file-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.upload-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-text {
  font-size: 12px;
  color: #909399;
}

.result-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-actions {
  display: flex;
  gap: 8px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 16px;
  padding: 24px 0;
}

:deep(.el-card__body) {
  padding: 24px;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-select) {
  width: 100%;
}

@media (max-width: 768px) {
  .upload-page {
    padding: 16px;
  }
  
  .file-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .file-actions {
    align-self: flex-end;
  }
  
  .action-buttons {
    flex-direction: column;
  }
}
</style>