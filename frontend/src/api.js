import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const askQuestion = (question) =>
  axios.post(`${BASE}/ask`, { question })
