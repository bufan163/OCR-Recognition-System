import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/utils/api'

export const useOcrStore = defineStore('ocr', () => {
  const uploadProgress = ref(0)
  const isUploading = ref(false)
  const results = ref([])
  const currentResult = ref(null)
  
  const uploadFile = async (file, options = {}) => {
    try {
      isUploading.value = true
      uploadProgress.value = 0
      
      const formData = new FormData()
      formData.append('file', file)
      
      if (options.engine) {
        formData.append('engine', options.engine)
      }
      if (options.language) {
        formData.append('language', options.language)
      }
      if (options.preprocessing) {
        formData.append('preprocessing', options.preprocessing)
      }
      
      const response = await api.post('/ocr/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          uploadProgress.value = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
        }
      })
      
      return response.data
    } catch (error) {
      throw error
    } finally {
      isUploading.value = false
      uploadProgress.value = 0
    }
  }
  
  const getResults = async (params = {}) => {
    try {
      const response = await api.get('/ocr/results', { params })
      results.value = response.data.items || response.data
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  const getResult = async (id) => {
    try {
      const response = await api.get(`/ocr/results/${id}`)
      currentResult.value = response.data
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  const deleteResult = async (id) => {
    try {
      await api.delete(`/ocr/results/${id}`)
      // 从列表中移除已删除的结果
      results.value = results.value.filter(result => result.id !== id)
      return true
    } catch (error) {
      throw error
    }
  }
  
  const getTaskStatus = async (taskId) => {
    try {
      const response = await api.get(`/ocr/task/${taskId}/status`)
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  const downloadResult = async (id, format = 'txt') => {
    try {
      const response = await api.get(`/ocr/results/${id}/download`, {
        params: { format },
        responseType: 'blob'
      })
      
      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `ocr_result_${id}.${format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      
      return true
    } catch (error) {
      throw error
    }
  }
  
  const getEngines = async () => {
    try {
      const response = await api.get('/ocr/engines')
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  const getStats = async () => {
    try {
      const response = await api.get('/ocr/stats')
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  return {
    uploadProgress,
    isUploading,
    results,
    currentResult,
    uploadFile,
    getResults,
    getResult,
    deleteResult,
    getTaskStatus,
    downloadResult,
    getEngines,
    getStats
  }
})