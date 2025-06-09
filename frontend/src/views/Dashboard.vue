<template>
  <div class="dashboard">
    <div class="dashboard-header">
      <h1>仪表盘</h1>
      <p>欢迎使用OCR识别系统</p>
    </div>
    
    <!-- 统计卡片 -->
    <div class="stats-grid">
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon size="32" color="#409EFF">
              <Document />
            </el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ stats.totalFiles || 0 }}</div>
            <div class="stat-label">总文件数</div>
          </div>
        </div>
      </el-card>
      
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon size="32" color="#67C23A">
              <Select />
            </el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ stats.successCount || 0 }}</div>
            <div class="stat-label">识别成功</div>
          </div>
        </div>
      </el-card>
      
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon size="32" color="#E6A23C">
              <Loading />
            </el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ stats.processingCount || 0 }}</div>
            <div class="stat-label">处理中</div>
          </div>
        </div>
      </el-card>
      
      <el-card class="stat-card" shadow="hover">
        <div class="stat-content">
          <div class="stat-icon">
            <el-icon size="32" color="#F56C6C">
              <Close />
            </el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-number">{{ stats.failedCount || 0 }}</div>
            <div class="stat-label">识别失败</div>
          </div>
        </div>
      </el-card>
    </div>
    
    <!-- 快速操作 -->
    <div class="quick-actions">
      <h2>快速操作</h2>
      <div class="actions-grid">
        <el-card class="action-card" shadow="hover" @click="$router.push('/upload')">
          <div class="action-content">
            <el-icon size="48" color="#409EFF">
              <Upload />
            </el-icon>
            <h3>上传文件</h3>
            <p>上传图片或PDF文件进行OCR识别</p>
          </div>
        </el-card>
        
        <el-card class="action-card" shadow="hover" @click="$router.push('/results')">
          <div class="action-content">
            <el-icon size="48" color="#67C23A">
              <List />
            </el-icon>
            <h3>查看结果</h3>
            <p>查看和管理所有识别结果</p>
          </div>
        </el-card>
        
        <el-card class="action-card" shadow="hover" @click="$router.push('/profile')">
          <div class="action-content">
            <el-icon size="48" color="#E6A23C">
              <User />
            </el-icon>
            <h3>个人设置</h3>
            <p>管理个人信息和系统设置</p>
          </div>
        </el-card>
      </div>
    </div>
    
    <!-- 最近结果 -->
    <div class="recent-results">
      <div class="section-header">
        <h2>最近结果</h2>
        <el-button type="primary" link @click="$router.push('/results')">
          查看全部
        </el-button>
      </div>
      
      <el-table 
        v-loading="loading"
        :data="recentResults" 
        style="width: 100%"
        empty-text="暂无数据"
      >
        <el-table-column prop="filename" label="文件名" min-width="200">
          <template #default="{ row }">
            <div class="filename-cell">
              <el-icon class="file-icon">
                <Picture v-if="isImageFile(row.filename)" />
                <Document v-else />
              </el-icon>
              <span class="filename">{{ row.filename }}</span>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag 
              :type="getStatusType(row.status)"
              size="small"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="engine" label="识别引擎" width="120" />
        
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button 
              type="primary" 
              link 
              size="small"
              @click="viewResult(row.id)"
            >
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useOcrStore } from '@/stores/ocr'
import { formatDateTime, isImageFile } from '@/utils'

const router = useRouter()
const ocrStore = useOcrStore()

const loading = ref(false)
const stats = ref({})
const recentResults = ref([])

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

const viewResult = (id) => {
  router.push(`/results/${id}`)
}

const loadStats = async () => {
  try {
    stats.value = await ocrStore.getStats()
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

const loadRecentResults = async () => {
  try {
    loading.value = true
    const response = await ocrStore.getResults({ 
      page: 1, 
      size: 5,
      sort: 'created_at',
      order: 'desc'
    })
    recentResults.value = response.items || response
  } catch (error) {
    console.error('加载最近结果失败:', error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadStats()
  loadRecentResults()
})
</script>

<style scoped>
.dashboard {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.dashboard-header {
  margin-bottom: 32px;
}

.dashboard-header h1 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 32px;
  font-weight: 600;
}

.dashboard-header p {
  margin: 0;
  color: #909399;
  font-size: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}

.stat-card {
  cursor: default;
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  flex-shrink: 0;
}

.stat-info {
  flex: 1;
}

.stat-number {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.quick-actions {
  margin-bottom: 40px;
}

.quick-actions h2 {
  margin: 0 0 20px 0;
  color: #303133;
  font-size: 20px;
  font-weight: 600;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.action-card {
  cursor: pointer;
  transition: transform 0.2s;
}

.action-card:hover {
  transform: translateY(-2px);
}

.action-content {
  text-align: center;
  padding: 20px;
}

.action-content h3 {
  margin: 16px 0 8px 0;
  color: #303133;
  font-size: 18px;
  font-weight: 600;
}

.action-content p {
  margin: 0;
  color: #909399;
  font-size: 14px;
  line-height: 1.5;
}

.recent-results {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  color: #303133;
  font-size: 20px;
  font-weight: 600;
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon {
  color: #909399;
}

.filename {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.el-card__body) {
  padding: 20px;
}

:deep(.el-table) {
  border-radius: 8px;
}
</style>