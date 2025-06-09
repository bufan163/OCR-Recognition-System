<template>
  <div class="results-page">
    <div class="results-header">
      <h1>识别结果</h1>
      <p>查看和管理所有OCR识别结果</p>
    </div>
    
    <!-- 搜索和筛选 -->
    <el-card class="filter-card" shadow="never">
      <el-form :model="filters" :inline="true" class="filter-form">
        <el-form-item label="文件名">
          <el-input
            v-model="filters.filename"
            placeholder="搜索文件名"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button icon="Search" @click="handleSearch" />
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="选择状态" clearable @change="handleSearch">
            <el-option label="全部" value="" />
            <el-option label="已完成" value="completed" />
            <el-option label="处理中" value="processing" />
            <el-option label="失败" value="failed" />
            <el-option label="等待中" value="pending" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="识别引擎">
          <el-select v-model="filters.engine" placeholder="选择引擎" clearable @change="handleSearch">
            <el-option label="全部" value="" />
            <el-option label="Tesseract" value="tesseract" />
            <el-option label="PaddleOCR" value="paddleocr" />
            <el-option label="EasyOCR" value="easyocr" />
            <el-option label="百度OCR" value="baidu" />
            <el-option label="腾讯OCR" value="tencent" />
          </el-select>
        </el-form-item>
        
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="handleSearch"
          />
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- 操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-button type="primary" @click="$router.push('/upload')">
          <el-icon><Upload /></el-icon>
          上传文件
        </el-button>
        
        <el-button 
          type="danger" 
          :disabled="selectedIds.length === 0"
          @click="handleBatchDelete"
        >
          <el-icon><Delete /></el-icon>
          批量删除 ({{ selectedIds.length }})
        </el-button>
      </div>
      
      <div class="toolbar-right">
        <el-button-group>
          <el-button 
            :type="viewMode === 'table' ? 'primary' : 'default'"
            @click="viewMode = 'table'"
          >
            <el-icon><List /></el-icon>
          </el-button>
          <el-button 
            :type="viewMode === 'grid' ? 'primary' : 'default'"
            @click="viewMode = 'grid'"
          >
            <el-icon><Grid /></el-icon>
          </el-button>
        </el-button-group>
        
        <el-button @click="handleRefresh">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>
    
    <!-- 表格视图 -->
    <el-card v-if="viewMode === 'table'" class="table-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="results"
        style="width: 100%"
        @selection-change="handleSelectionChange"
        empty-text="暂无数据"
      >
        <el-table-column type="selection" width="55" />
        
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="filename-cell">
              <el-icon class="file-icon">
                <Picture v-if="isImageFile(row.filename)" />
                <Document v-else />
              </el-icon>
              <span class="filename" :title="row.filename">{{ row.filename }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="engine" label="识别引擎" width="120" />
        
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="{ row }">
            <span v-if="row.confidence">{{ (row.confidence * 100).toFixed(1) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="processing_time" label="处理时间" width="100">
          <template #default="{ row }">
            <span v-if="row.processing_time">{{ row.processing_time.toFixed(2) }}s</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewResult(row.id)">
              查看
            </el-button>
            
            <el-dropdown @command="(command) => handleAction(command, row)">
              <el-button type="primary" link size="small">
                更多<el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="download" :disabled="row.status !== 'completed'">
                    <el-icon><Download /></el-icon>下载结果
                  </el-dropdown-item>
                  <el-dropdown-item command="copy" :disabled="row.status !== 'completed'">
                    <el-icon><CopyDocument /></el-icon>复制文本
                  </el-dropdown-item>
                  <el-dropdown-item command="reprocess">
                    <el-icon><Refresh /></el-icon>重新识别
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <el-icon><Delete /></el-icon>删除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    
    <!-- 网格视图 -->
    <div v-else class="grid-view">
      <div v-loading="loading" class="grid-container">
        <div 
          v-for="item in results" 
          :key="item.id" 
          class="grid-item"
          @click="viewResult(item.id)"
        >
          <el-card class="result-card" shadow="hover">
            <div class="card-header">
              <el-checkbox 
                :model-value="selectedIds.includes(item.id)"
                @change="(checked) => handleItemSelect(item.id, checked)"
                @click.stop
              />
              <el-tag :type="getStatusType(item.status)" size="small">
                {{ getStatusText(item.status) }}
              </el-tag>
            </div>
            
            <div class="card-content">
              <div class="file-preview">
                <el-icon class="file-icon" size="48">
                  <Picture v-if="isImageFile(item.filename)" />
                  <Document v-else />
                </el-icon>
              </div>
              
              <div class="file-info">
                <div class="filename" :title="item.filename">{{ item.filename }}</div>
                <div class="file-meta">
                  <span>{{ item.engine }}</span>
                  <span v-if="item.confidence">{{ (item.confidence * 100).toFixed(1) }}%</span>
                </div>
                <div class="file-time">{{ formatRelativeTime(item.created_at) }}</div>
              </div>
            </div>
            
            <div class="card-actions" @click.stop>
              <el-button type="primary" link size="small" @click="viewResult(item.id)">
                查看详情
              </el-button>
              <el-button 
                type="success" 
                link 
                size="small" 
                :disabled="item.status !== 'completed'"
                @click="downloadResult(item.id)"
              >
                下载
              </el-button>
            </div>
          </el-card>
        </div>
      </div>
      
      <el-empty v-if="!loading && results.length === 0" description="暂无数据" />
    </div>
    
    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload, Delete, List, Grid, Refresh, Search, Download, 
  CopyDocument, Picture, Document, ArrowDown
} from '@element-plus/icons-vue'
import { useOcrStore } from '@/stores/ocr'
import { formatDateTime, formatRelativeTime, isImageFile, copyToClipboard } from '@/utils'

const router = useRouter()
const ocrStore = useOcrStore()

const loading = ref(false)
const viewMode = ref('table')
const results = ref([])
const selectedIds = ref([])

const filters = reactive({
  filename: '',
  status: '',
  engine: '',
  dateRange: null
})

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
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
    'completed': '已完成',
    'processing': '处理中',
    'failed': '失败',
    'pending': '等待中'
  }
  return statusMap[status] || status
}

const loadResults = async () => {
  try {
    loading.value = true
    
    const params = {
      page: pagination.page,
      size: pagination.size,
      ...filters
    }
    
    // 处理日期范围
    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }
    
    const response = await ocrStore.getResults(params)
    
    if (response.items) {
      results.value = response.items
      pagination.total = response.total || 0
    } else {
      results.value = response
      pagination.total = response.length
    }
    
  } catch (error) {
    console.error('加载结果失败:', error)
    ElMessage.error('加载结果失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadResults()
}

const handleRefresh = () => {
  loadResults()
}

const handlePageChange = (page) => {
  pagination.page = page
  loadResults()
}

const handleSizeChange = (size) => {
  pagination.size = size
  pagination.page = 1
  loadResults()
}

const handleSelectionChange = (selection) => {
  selectedIds.value = selection.map(item => item.id)
}

const handleItemSelect = (id, checked) => {
  if (checked) {
    if (!selectedIds.value.includes(id)) {
      selectedIds.value.push(id)
    }
  } else {
    const index = selectedIds.value.indexOf(id)
    if (index > -1) {
      selectedIds.value.splice(index, 1)
    }
  }
}

const viewResult = (id) => {
  router.push(`/results/${id}`)
}

const downloadResult = async (id) => {
  try {
    await ocrStore.downloadResult(id, 'txt')
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

const copyResultText = async (item) => {
  try {
    const result = await ocrStore.getResult(item.id)
    if (result.text) {
      const success = await copyToClipboard(result.text)
      if (success) {
        ElMessage.success('文本已复制到剪贴板')
      } else {
        ElMessage.error('复制失败')
      }
    } else {
      ElMessage.warning('没有可复制的文本')
    }
  } catch (error) {
    ElMessage.error('获取文本失败')
  }
}

const deleteResult = async (id) => {
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
    
    await ocrStore.deleteResult(id)
    ElMessage.success('删除成功')
    loadResults()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 个识别结果吗？此操作不可恢复。`,
      '确认批量删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    for (const id of selectedIds.value) {
      await ocrStore.deleteResult(id)
    }
    
    ElMessage.success('批量删除成功')
    selectedIds.value = []
    loadResults()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  }
}

const handleAction = async (command, row) => {
  switch (command) {
    case 'download':
      await downloadResult(row.id)
      break
    case 'copy':
      await copyResultText(row)
      break
    case 'reprocess':
      ElMessage.info('重新识别功能开发中')
      break
    case 'delete':
      await deleteResult(row.id)
      break
  }
}

onMounted(() => {
  loadResults()
})
</script>

<style scoped>
.results-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.results-header {
  margin-bottom: 32px;
}

.results-header h1 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 32px;
  font-weight: 600;
}

.results-header p {
  margin: 0;
  color: #909399;
  font-size: 16px;
}

.filter-card {
  margin-bottom: 24px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding: 16px 0;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-card {
  margin-bottom: 24px;
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #909399;
  flex-shrink: 0;
}

.filename {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.grid-view {
  margin-bottom: 24px;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  min-height: 200px;
}

.grid-item {
  cursor: pointer;
}

.result-card {
  height: 100%;
  transition: transform 0.2s;
}

.result-card:hover {
  transform: translateY(-2px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-content {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.file-preview {
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  border-radius: 8px;
  flex-shrink: 0;
}

.file-info {
  flex: 1;
  min-width: 0;
}

.file-info .filename {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.file-time {
  font-size: 12px;
  color: #c0c4cc;
}

.card-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination {
  display: flex;
  justify-content: center;
  padding: 24px 0;
}

:deep(.el-card__body) {
  padding: 20px;
}

:deep(.el-table) {
  border-radius: 8px;
}

:deep(.el-form-item) {
  margin-bottom: 0;
}

@media (max-width: 768px) {
  .results-page {
    padding: 16px;
  }
  
  .toolbar {
    flex-direction: column;
    gap: 16px;
    align-items: stretch;
  }
  
  .toolbar-left,
  .toolbar-right {
    justify-content: center;
  }
  
  .filter-form {
    flex-direction: column;
  }
  
  .grid-container {
    grid-template-columns: 1fr;
  }
}
</style>