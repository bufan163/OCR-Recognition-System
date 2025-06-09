<template>
  <div class="profile-page">
    <div class="profile-header">
      <h1>个人设置</h1>
      <p>管理您的个人信息和系统偏好设置</p>
    </div>
    
    <div class="profile-content">
      <!-- 个人信息 -->
      <el-card class="profile-card" shadow="never">
        <template #header>
          <span>个人信息</span>
        </template>
        
        <el-form
          ref="profileFormRef"
          :model="profileForm"
          :rules="profileRules"
          label-width="100px"
          class="profile-form"
        >
          <el-form-item label="头像">
            <div class="avatar-section">
              <el-avatar :size="80" :src="profileForm.avatar" class="avatar">
                <el-icon><User /></el-icon>
              </el-avatar>
              <div class="avatar-actions">
                <el-upload
                  :show-file-list="false"
                  :before-upload="beforeAvatarUpload"
                  :on-success="handleAvatarSuccess"
                  action="/api/users/avatar"
                  :headers="{ Authorization: `Bearer ${userStore.token}` }"
                >
                  <el-button size="small">更换头像</el-button>
                </el-upload>
                <el-button size="small" @click="removeAvatar">移除</el-button>
              </div>
            </div>
          </el-form-item>
          
          <el-form-item label="用户名" prop="username">
            <el-input v-model="profileForm.username" :disabled="true" />
            <div class="form-tip">用户名不可修改</div>
          </el-form-item>
          
          <el-form-item label="邮箱" prop="email">
            <el-input v-model="profileForm.email" />
          </el-form-item>
          
          <el-form-item label="昵称" prop="nickname">
            <el-input v-model="profileForm.nickname" placeholder="请输入昵称" />
          </el-form-item>
          
          <el-form-item label="手机号" prop="phone">
            <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
          </el-form-item>
          
          <el-form-item label="个人简介">
            <el-input
              v-model="profileForm.bio"
              type="textarea"
              :rows="3"
              placeholder="介绍一下自己吧"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" :loading="saving" @click="saveProfile">
              保存信息
            </el-button>
            <el-button @click="resetProfile">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
      
      <!-- 修改密码 -->
      <el-card class="password-card" shadow="never">
        <template #header>
          <span>修改密码</span>
        </template>
        
        <el-form
          ref="passwordFormRef"
          :model="passwordForm"
          :rules="passwordRules"
          label-width="100px"
          class="password-form"
        >
          <el-form-item label="当前密码" prop="currentPassword">
            <el-input
              v-model="passwordForm.currentPassword"
              type="password"
              placeholder="请输入当前密码"
              show-password
            />
          </el-form-item>
          
          <el-form-item label="新密码" prop="newPassword">
            <el-input
              v-model="passwordForm.newPassword"
              type="password"
              placeholder="请输入新密码"
              show-password
            />
          </el-form-item>
          
          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="passwordForm.confirmPassword"
              type="password"
              placeholder="请再次输入新密码"
              show-password
            />
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" :loading="changingPassword" @click="changePassword">
              修改密码
            </el-button>
            <el-button @click="resetPasswordForm">重置</el-button>
          </el-form-item>
        </el-form>
      </el-card>
      
      <!-- 系统设置 -->
      <el-card class="settings-card" shadow="never">
        <template #header>
          <span>系统设置</span>
        </template>
        
        <div class="settings-content">
          <div class="setting-item">
            <div class="setting-info">
              <div class="setting-title">默认识别引擎</div>
              <div class="setting-desc">选择您偏好的OCR识别引擎</div>
            </div>
            <el-select v-model="settings.defaultEngine" @change="saveSettings">
              <el-option label="PaddleOCR" value="paddleocr" />
              <el-option label="Tesseract" value="tesseract" />
              <el-option label="EasyOCR" value="easyocr" />
              <el-option label="百度OCR" value="baidu" />
              <el-option label="腾讯OCR" value="tencent" />
            </el-select>
          </div>
          
          <el-divider />
          
          <div class="setting-item">
            <div class="setting-info">
              <div class="setting-title">默认识别语言</div>
              <div class="setting-desc">设置默认的文字识别语言</div>
            </div>
            <el-select v-model="settings.defaultLanguage" @change="saveSettings">
              <el-option label="中文" value="zh" />
              <el-option label="英文" value="en" />
              <el-option label="中英文混合" value="zh-en" />
            </el-select>
          </div>
          
          <el-divider />
          
          <div class="setting-item">
            <div class="setting-info">
              <div class="setting-title">自动保存结果</div>
              <div class="setting-desc">识别完成后自动保存到本地</div>
            </div>
            <el-switch v-model="settings.autoSave" @change="saveSettings" />
          </div>
          
          <el-divider />
          
          <div class="setting-item">
            <div class="setting-info">
              <div class="setting-title">邮件通知</div>
              <div class="setting-desc">识别完成后发送邮件通知</div>
            </div>
            <el-switch v-model="settings.emailNotification" @change="saveSettings" />
          </div>
          
          <el-divider />
          
          <div class="setting-item">
            <div class="setting-info">
              <div class="setting-title">数据保留时间</div>
              <div class="setting-desc">识别结果在系统中的保留天数</div>
            </div>
            <el-select v-model="settings.dataRetention" @change="saveSettings">
              <el-option label="7天" :value="7" />
              <el-option label="30天" :value="30" />
              <el-option label="90天" :value="90" />
              <el-option label="永久保留" :value="-1" />
            </el-select>
          </div>
        </div>
      </el-card>
      
      <!-- 账户统计 -->
      <el-card class="stats-card" shadow="never">
        <template #header>
          <span>账户统计</span>
        </template>
        
        <div class="stats-grid">
          <div class="stat-item">
            <div class="stat-number">{{ userStats.totalFiles || 0 }}</div>
            <div class="stat-label">总文件数</div>
          </div>
          
          <div class="stat-item">
            <div class="stat-number">{{ userStats.successCount || 0 }}</div>
            <div class="stat-label">识别成功</div>
          </div>
          
          <div class="stat-item">
            <div class="stat-number">{{ formatFileSize(userStats.totalSize || 0) }}</div>
            <div class="stat-label">总文件大小</div>
          </div>
          
          <div class="stat-item">
            <div class="stat-number">{{ userStats.totalTime || 0 }}s</div>
            <div class="stat-label">总处理时间</div>
          </div>
        </div>
      </el-card>
      
      <!-- 危险操作 -->
      <el-card class="danger-card" shadow="never">
        <template #header>
          <span>危险操作</span>
        </template>
        
        <div class="danger-content">
          <div class="danger-item">
            <div class="danger-info">
              <div class="danger-title">清空所有数据</div>
              <div class="danger-desc">删除所有识别结果和相关文件，此操作不可恢复</div>
            </div>
            <el-button type="danger" @click="clearAllData">清空数据</el-button>
          </div>
          
          <el-divider />
          
          <div class="danger-item">
            <div class="danger-info">
              <div class="danger-title">删除账户</div>
              <div class="danger-desc">永久删除您的账户和所有相关数据，此操作不可恢复</div>
            </div>
            <el-button type="danger" @click="deleteAccount">删除账户</el-button>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { User } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { formatFileSize } from '@/utils'
import api from '@/utils/api'

const userStore = useUserStore()

const profileFormRef = ref()
const passwordFormRef = ref()
const saving = ref(false)
const changingPassword = ref(false)

const profileForm = reactive({
  username: '',
  email: '',
  nickname: '',
  phone: '',
  bio: '',
  avatar: ''
})

const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const settings = reactive({
  defaultEngine: 'paddleocr',
  defaultLanguage: 'zh-en',
  autoSave: true,
  emailNotification: false,
  dataRetention: 30
})

const userStats = reactive({
  totalFiles: 0,
  successCount: 0,
  totalSize: 0,
  totalTime: 0
})

const profileRules = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }
  ],
  phone: [
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ]
}

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== passwordForm.newPassword) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const passwordRules = {
  currentPassword: [
    { required: true, message: '请输入当前密码', trigger: 'blur' }
  ],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 20, message: '密码长度在6到20个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ]
}

const loadProfile = async () => {
  try {
    const user = await userStore.getCurrentUser()
    Object.assign(profileForm, {
      username: user.username,
      email: user.email,
      nickname: user.nickname || '',
      phone: user.phone || '',
      bio: user.bio || '',
      avatar: user.avatar || ''
    })
  } catch (error) {
    console.error('加载用户信息失败:', error)
  }
}

const loadSettings = async () => {
  try {
    const response = await api.get('/users/settings')
    Object.assign(settings, response.data)
  } catch (error) {
    console.error('加载设置失败:', error)
  }
}

const loadStats = async () => {
  try {
    const response = await api.get('/users/stats')
    Object.assign(userStats, response.data)
  } catch (error) {
    console.error('加载统计数据失败:', error)
  }
}

const saveProfile = async () => {
  if (!profileFormRef.value) return
  
  try {
    await profileFormRef.value.validate()
    saving.value = true
    
    await userStore.updateProfile({
      email: profileForm.email,
      nickname: profileForm.nickname,
      phone: profileForm.phone,
      bio: profileForm.bio
    })
    
    ElMessage.success('个人信息保存成功')
    
  } catch (error) {
    console.error('保存失败:', error)
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

const resetProfile = () => {
  loadProfile()
}

const changePassword = async () => {
  if (!passwordFormRef.value) return
  
  try {
    await passwordFormRef.value.validate()
    changingPassword.value = true
    
    await api.put('/users/password', {
      current_password: passwordForm.currentPassword,
      new_password: passwordForm.newPassword
    })
    
    ElMessage.success('密码修改成功')
    resetPasswordForm()
    
  } catch (error) {
    console.error('修改密码失败:', error)
    if (error.response?.status === 400) {
      ElMessage.error('当前密码错误')
    } else {
      ElMessage.error('修改密码失败，请稍后重试')
    }
  } finally {
    changingPassword.value = false
  }
}

const resetPasswordForm = () => {
  Object.assign(passwordForm, {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  passwordFormRef.value?.clearValidate()
}

const saveSettings = async () => {
  try {
    await api.put('/users/settings', settings)
    ElMessage.success('设置保存成功')
  } catch (error) {
    console.error('保存设置失败:', error)
    ElMessage.error('保存设置失败')
  }
}

const beforeAvatarUpload = (file) => {
  const isImage = /^image\/(jpeg|jpg|png|gif)$/.test(file.type)
  const isLt2M = file.size / 1024 / 1024 < 2
  
  if (!isImage) {
    ElMessage.error('头像只能是 JPG/PNG/GIF 格式!')
    return false
  }
  if (!isLt2M) {
    ElMessage.error('头像大小不能超过 2MB!')
    return false
  }
  return true
}

const handleAvatarSuccess = (response) => {
  profileForm.avatar = response.avatar_url
  ElMessage.success('头像上传成功')
}

const removeAvatar = async () => {
  try {
    await api.delete('/users/avatar')
    profileForm.avatar = ''
    ElMessage.success('头像移除成功')
  } catch (error) {
    ElMessage.error('移除头像失败')
  }
}

const clearAllData = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有数据吗？这将删除您的所有识别结果和文件，此操作不可恢复！',
      '危险操作确认',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger'
      }
    )
    
    await api.delete('/users/data')
    ElMessage.success('数据清空成功')
    loadStats()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('清空数据失败')
    }
  }
}

const deleteAccount = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要删除账户吗？这将永久删除您的账户和所有相关数据，此操作不可恢复！',
      '危险操作确认',
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger'
      }
    )
    
    await api.delete('/users/account')
    ElMessage.success('账户删除成功')
    await userStore.logout()
    
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除账户失败')
    }
  }
}

onMounted(() => {
  loadProfile()
  loadSettings()
  loadStats()
})
</script>

<style scoped>
.profile-page {
  padding: 24px;
  max-width: 800px;
  margin: 0 auto;
}

.profile-header {
  margin-bottom: 32px;
}

.profile-header h1 {
  margin: 0 0 8px 0;
  color: #303133;
  font-size: 32px;
  font-weight: 600;
}

.profile-header p {
  margin: 0;
  color: #909399;
  font-size: 16px;
}

.profile-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.avatar-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar {
  border: 2px solid #ebeef5;
}

.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.settings-content {
  display: flex;
  flex-direction: column;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
}

.setting-info {
  flex: 1;
}

.setting-title {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.setting-desc {
  font-size: 14px;
  color: #909399;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 24px;
}

.stat-item {
  text-align: center;
}

.stat-number {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.danger-content {
  display: flex;
  flex-direction: column;
}

.danger-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
}

.danger-info {
  flex: 1;
}

.danger-title {
  font-size: 16px;
  font-weight: 500;
  color: #f56c6c;
  margin-bottom: 4px;
}

.danger-desc {
  font-size: 14px;
  color: #909399;
}

.danger-card {
  border: 1px solid #fbc4c4;
}

.danger-card :deep(.el-card__header) {
  background: #fef0f0;
  color: #f56c6c;
}

:deep(.el-card__body) {
  padding: 24px;
}

:deep(.el-card__header) {
  padding: 16px 24px;
  border-bottom: 1px solid #ebeef5;
  font-weight: 600;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-divider) {
  margin: 0;
}

@media (max-width: 768px) {
  .profile-page {
    padding: 16px;
  }
  
  .avatar-section {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .setting-item,
  .danger-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>