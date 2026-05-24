import axios from 'axios'

const BASE = 'http://localhost:8000'

export const askQuestion = (question) =>
  axios.post(`${BASE}/ask`, { question })
