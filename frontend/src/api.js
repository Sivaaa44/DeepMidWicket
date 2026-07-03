import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const getStoredToken = () => localStorage.getItem('ciq_token')
export const clearStoredToken = () => localStorage.removeItem('ciq_token')

export const authSignup = async (email, username, password) => {
  const { data } = await axios.post(`${BASE}/auth/signup`, { email, username, password })
  if (data?.access_token) {
    localStorage.setItem('ciq_token', data.access_token)
  }
  return data
}

export const authLogin = async (email, password) => {
  const { data } = await axios.post(`${BASE}/auth/login`, { email, password })
  if (data?.access_token) {
    localStorage.setItem('ciq_token', data.access_token)
  }
  return data
}

export const getMe = async (token) => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  const { data } = await axios.get(`${BASE}/auth/me`, { headers })
  return data
}

export const askQuestion = (question, session_id, token) => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  return axios.post(`${BASE}/ask`, { question, session_id }, { headers })
}
