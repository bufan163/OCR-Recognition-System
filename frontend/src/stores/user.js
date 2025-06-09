import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  
  const isLoggedIn = computed(() => !!token.value)
  
  const login = async (credentials) => {
    try {
      const response = await api.post('/auth/login', credentials)
      const { access_token, user: userData } = response.data
      
      token.value = access_token
      user.value = userData
      localStorage.setItem('token', access_token)
      
      // 设置默认请求头
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  const register = async (userData) => {
    try {
      const response = await api.post('/auth/register', userData)
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } catch (error) {
      // 即使请求失败也要清除本地数据
    } finally {
      token.value = ''
      user.value = null
      localStorage.removeItem('token')
      delete api.defaults.headers.common['Authorization']
    }
  }
  
  const getCurrentUser = async () => {
    try {
      const response = await api.get('/auth/me')
      user.value = response.data
      return response.data
    } catch (error) {
      // 如果获取用户信息失败，清除登录状态
      await logout()
      throw error
    }
  }
  
  const updateProfile = async (profileData) => {
    try {
      const response = await api.put('/users/profile', profileData)
      user.value = { ...user.value, ...response.data }
      return response.data
    } catch (error) {
      throw error
    }
  }
  
  // 初始化时设置请求头
  if (token.value) {
    api.defaults.headers.common['Authorization'] = `Bearer ${token.value}`
  }
  
  return {
    user,
    token,
    isLoggedIn,
    login,
    register,
    logout,
    getCurrentUser,
    updateProfile
  }
})