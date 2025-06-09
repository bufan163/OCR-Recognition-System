<template>
  <div class="result-detail">
    <div v-loading="loading" class="detail-container">
      <!-- 头部导航 -->
      <div class="detail-header">
        <el-button @click="$router.back()">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        
        <div class="header-actions">
          <el-button type="primary" @click="downloadResult">
            <el-icon><Download /></el-icon>
            下载结果
          </el-button>
          
          <el-dropdown @command="handleAction">
            <el-button>
              更多操作<el-icon class="el-icon--right"><arrow-down /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="copy">
                  <el-icon><CopyDocument /></el-icon>复制文本
                </el-dropdown-item>
                <el-dropdown-item command="export-json">
                  <el-icon><Download /></el-icon>导出JSON
                </el-dropdown-item>
                <el-dropdown-item command="export-pdf">
                  <el-icon><Download /></el-icon>导出PDF
                </el-dropdown-item>
                <el-dropdown-item command="reprocess" divided>
                  <el-icon><Refresh /></el-icon>重新识别
                </el-dropdown-item>
                <el-dropdown-item command="delete">
                  <el-icon><Delete /></el-icon>删除结果
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
      
      <div v-if="result" class="detail-content">
        <!-- 文件信息 -->
        <el-card class="info-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>文件信息</span>
              <el-tag :type="getStatusType(result.status)" size="large">
                {{ getStatusText(result.status) }}
              </el-tag>
            </div>
          </template>
          
          <div class="file-info">
            <div class="file-preview">
              <div v-if="result.file_url" class="preview-container">
                <img 
                  v-if="isImageFile(result.filename)"
                  :src="result.file_url"
                  :alt="result.filename"
                  class="preview-image"
                  @error="handleImageError"
                />
                <div v-else class="pdf-preview">
                  <el-icon size="64"><Document /></el-icon>
                  <p>PDF文件</p>
                </div>
              </div>
              <div v-else class="no-preview">
                <el-icon size="64"><Picture /></el-icon>
                <p>无预览</p>
              </div>
            </div>
            
            <div class="file-details">
              <div class="detail-row">
                <label>文件名：</label>
                <span>{{ result.filename }}</span>
              </div>
              
              <div class="detail-row">
                <label>文件大小：</label>
                <span>{{ formatFileSize(result.file_size) }}</span>
              </div>
              
              <div class="detail-row">
                <label>识别引擎：</label>
                <span>{{ result.engine }}</span>
              </div>
              
              <div class="detail-row">
                <label>识别语言：</label>
                <span>{{ result.language || '自动检测' }}</span>
              </div>
              
              <div class="detail-row">
                <label>置信度：</label>
                <span v-if="result.confidence">
                  {{ (result.confidence * 100).toFixed(1) }}%
                </span>
                <span v-else>-</span>
              </div>
              
              <div class="detail-row">
                <label>处理时间：</label>
                <span v-if="result.processing_time">
                  {{ result.processing_time.toFixed(2) }}秒
                </span>
                <span v-else>-</span>
              </div>
              
              <div class="detail-row">
                <label>创建时间：</label>
                <span>{{ formatDateTime(result.created_at) }}</span>
              </div>
              
              <div class="detail-row">
                <label>更新时间：</label>
                <span>{{ formatDateTime(result.updated_at) }}</span>
              </div>
            </div>
          </div>
        </el-card>
        
        <!-- 识别结果 -->
        <el-card class="result-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>识别结果</span>
              <div class="result-actions">
                <el-button size="small" @click="copyText">
                  <el-icon><CopyDocument /></el-icon>
                  复制文本
                </el-button>
                <el-button size="small" @click="toggleTextMode">
                  <el-icon><Edit /></el-icon>
                  {{ textMode === 'view' ? '编辑' : '预览' }}
                </el-button>
              </div>
            </div>
          </template>
          
          <div v-if="result.status === 'completed'" class="result-content">
            <!-- 文本结果 -->
            <div v-if="result.text" class="text-result">
              <div v-if="textMode === 'view'" class="text-view">
                <pre class="text-content">{{ result.text }}</pre>
              </div>
              <div v-else class="text-edit">
                <el-input
                  v-model="editableText"
                  type="textarea"
                  :rows="20"
                  placeholder="识别的文本内容"
                  class="text-editor"
                />
                <div class="edit-actions">
                  <el-button @click="cancelEdit">取消</el-button>
                  <el-button type="primary" @click="saveEdit">保存</el-button>
                </div>
              </div>
            </div>
            
            <!-- 结构化结果 -->
            <div v-if="result.structured_data" class="structured-result">
              <h3>结构化数据</h3>
              <el-tree
                :data="structuredTreeData"
                :props="{ children: 'children', label: 'label' }"
                default-expand-all
                class="structured-tree"
              />
            </div>
            
            <!-- 位置信息 -->
            <div v-if="result.bounding_boxes && result.bounding_boxes.length > 0" class="position-result">
              <h3>文字位置信息</h3>
              <div class="position-controls">
                <el-switch
                  v-model="showBoundingBoxes"
                  active-text="显示边界框"
                  inactive-text="隐藏边界框"
                />
              </div>
              
              <div v-if="showBoundingBoxes" class="bounding-boxes">
                <div 
                  v-for="(box, index) in result.bounding_boxes" 
                  :key="index"
                  class="box-item"
                >
                  <div class="box-text">{{ box.text }}</div>
                  <div class="box-coords">
                    位置: ({{ box.x }}, {{ box.y }}) 
                    大小: {{ box.width }} × {{ box.height }}
                    置信度: {{ (box.confidence * 100).toFixed(1) }}%
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          <div v-else-if="result.status === 'processing'" class="processing-status">
            <el-icon class="is-loading"><Loading /></el-icon>
            <p>正在处理中，请稍候...</p>
          </div>
          
          <div v-else-if="result.status === 'failed'" class="error-status">
            <el-icon><Warning /></el-icon>
            <p>识别失败</p>
            <div v-if="result.error_message" class="error-message">
              <strong>错误信息：</strong>{{ result.error_message }}
            </div>
          </div>
          
          <div v-else class="pending-status">
            <el-icon><Clock /></el-icon>
            <p>等待处理中...</p>
          </div>
        </el-card>
        
        <!-- 处理日志 -->
        <el-card v-if="result.logs && result.logs.length > 0" class="logs-card" shadow="never">
          <template #header>
            <span>处理日志</span>
          </template>
          
          <el-timeline>
            <el-timeline-item
              v-for="(log, index) in result.logs"
              :key="index"
              :timestamp="formatDateTime(log.timestamp)"
              :type="getLogType(log.level)"
            >
              <div class="log-content">
                <div class="log-level">{{ log.level.toUpperCase() }}</div>
                <div class="log-message">{{ log.message }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </div>
      
      <el-empty v-else-if="!loading" description="结果不存在或已被删除" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Download, CopyDocument, Refresh, Delete, Edit,
  Document, Picture, Loading, Warning, Clock, ArrowDown
} from '@element-plus/icons-vue'
import { useOcrStore } from '@/stores/ocr'
import { formatDateTime, formatFileSize, isImageFile, copyToClipboard } from '@/utils'

const route = useRoute()
const router = useRouter()
const ocrStore = useOcrStore()

const loading = ref(false)
const result = ref(null)
const textMode = ref('view')
const editableText = ref('')
const showBoundingBoxes = ref(false)

const structuredTreeData = computed(() => {
  if (!result.value?.structured_data) return []
  
  const convertToTree = (obj, key = 'root') => {
    if (typeof obj === 'object' && obj !== null) {
      if (Array.isArray(obj)) {
        return {
          label: `${key} (${obj.length} items)`,
          children: obj.map((item, index) => convertToTree(item, `[${index}]`))
        }
      } else {
        return {
          label: key,
          children: Object.entries(obj).map(([k, v]) => convertToTree(v, k))
        }
      }
    } else {
      return {
        label: `${key}: ${obj}`
      }
    }
  }
  
  return [convertToTree(result.value.structured_data, '结构化数据')]
})

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
    'processing': '处理中',
    'failed': '识别失败',
    'pending': '等待处理'
  }
  return statusMap[status] || status
}

const getLogType = (level) => {
  const typeMap = {
    'error': 'danger',
    'warning': 'warning',
    'info': 'primary',
    'debug': 'info'
  }
  return typeMap[level.toLowerCase()] || 'info'
}

const loadResult = async () => {
  try {
    loading.value = true
    const id = route.params.id
    result.value = await ocrStore.getResult(id)
    editableText.value = result.value.text || ''
  } catch (error) {
    console.error('加载结果失败:', error)
    ElMessage.error('加载结果失败')
  } finally {
    loading.value = false
  }
}

const downloadResult = async () => {
  try {
    await ocrStore.downloadResult(result.value.id, 'txt')
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const copyText = async () => {
  if (!result.value.text) {
    ElMessage.warning('没有可复制的文本')
    return
  }
  
  const success = await copyToClipboard(result.value.text)
  if (success) {
    ElMessage.success('文本已复制到剪贴板')
  } else {
    ElMessage.error('复制失败')
  }
}

const toggleTextMode = () => {
  if (textMode.value === 'view') {
    textMode.value = 'edit'
    editableText.value = result.value.text || ''
  } else {
    textMode.value = 'view'
  }
}

const cancelEdit = () => {
  textMode.value = 'view'
  editableText.value = result.value.text || ''
}

const saveEdit = async () => {
  try {
    // 这里应该调用API保存编辑后的文本
    // await ocrStore.updateResultText(result.value.id, editableText.value)
    
    result.value.text = editableText.value
    textMode.value = 'view'
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const handleImageError = (event) => {
  event.target.style.display = 'none'
}

const handleAction = async (command) => {
  switch (command) {
    case 'copy':
      await copyText()
      break
    case 'export-json':
      await exportResult('json')
      break
    case 'export-pdf':
      await exportResult('pdf')
      break
    case 'reprocess':
      ElMessage.info('重新识别功能开发中')
      break
    case 'delete':
      await deleteResult()
      break
  }
}

const exportResult = async (format) => {
  try {
    await ocrStore.downloadResult(result.value.id, format)
    ElMessage.success(`导出${format.toUpperCase()}成功`)
  } catch (error) {
    ElMessage.error(`导出${format.toUpperCase()}失败`)
  }
}

const deleteResult = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除这个识别结果吗？此操作不可恢复。',
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await ocrStore.deleteResult(result.value.id)
    ElMessage.success('删除成功')
    router.push('/results')
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadResult()
})
</script>

<style scoped>
.result-detail {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-card .file-info {
  display: flex;
  gap: 24px;
}

.file-preview {
  width: 200px;
  flex-shrink: 0;
}

.preview-container {
  width: 100%;
  height: 200px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.pdf-preview,
.no-preview {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.file-details {
  flex: 1;
}

.detail-row {
  display: flex;
  margin-bottom: 12px;
  align-items: center;
}

.detail-row label {
  width: 100px;
  color: #606266;
  font-weight: 500;
  flex-shrink: 0;
}

.detail-row span {
  color: #303133;
  word-break: break-all;
}

.result-actions {
  display: flex;
  gap: 8px;
}

.text-result {
  margin-bottom: 24px;
}

.text-view {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fafafa;
}

.text-content {
  padding: 16px;
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
  max-height: 400px;
  overflow-y: auto;
}

.text-edit {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.text-editor {
  font-family: 'Courier New', monospace;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.structured-result,
.position-result {
  margin-bottom: 24px;
}

.structured-result h3,
.position-result h3 {
  margin: 0 0 16px 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.structured-tree {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}

.position-controls {
  margin-bottom: 16px;
}

.bounding-boxes {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fafafa;
}

.box-item {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.box-item:last-child {
  border-bottom: none;
}

.box-text {
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.box-coords {
  font-size: 12px;
  color: #909399;
}

.processing-status,
.error-status,
.pending-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #909399;
}

.processing-status .el-icon,
.error-status .el-icon,
.pending-status .el-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-message {
  margin-top: 16px;
  padding: 12px;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 4px;
  color: #f56c6c;
  font-size: 14px;
}

.log-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-level {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  background: #f0f2f5;
  color: #606266;
}

.log-message {
  flex: 1;
  color: #303133;
}

:deep(.el-card__body) {
  padding: 24px;
}

:deep(.el-card__header) {
  padding: 16px 24px;
  border-bottom: 1px solid #ebeef5;
}

:deep(.el-tree) {
  background: transparent;
}

:deep(.el-timeline) {
  padding-left: 0;
}

@media (max-width: 768px) {
  .result-detail {
    padding: 16px;
  }
  
  .detail-header {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .header-actions {
    justify-content: center;
  }
  
  .file-info {
    flex-direction: column;
  }
  
  .file-preview {
    width: 100%;
  }
  
  .detail-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .detail-row label {
    width: auto;
  }
}
</style>