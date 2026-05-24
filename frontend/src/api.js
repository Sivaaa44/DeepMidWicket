import axios from 'axios'

const client = axios.create({
  baseURL: 'http://localhost:8000',
  headers: { 'Content-Type': 'application/json' },
  timeout: 120000,
})

export async function askQuestion(question) {
  const { data } = await client.post('/ask', { question })
  return data
}
