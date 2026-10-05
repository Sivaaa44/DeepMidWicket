const BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')
const TOKEN_KEY = 'ciq_token'

export const getStoredToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export const setStoredToken = (token) => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* storage unavailable: the session simply won't persist */
  }
}

export class ApiError extends Error {
  constructor(message, { status = 0, code = null, data = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.data = data
  }
}

const FALLBACK_MESSAGES = {
  0: "Can't reach the server. Check your connection and try again.",
  401: 'Please sign in again.',
  403: "You don't have access to that.",
  404: 'Not found.',
  422: 'That request was invalid.',
  429: 'Too many requests. Please slow down.',
  500: 'Something went wrong on our side.',
  502: 'The server is restarting. Try again in a moment.',
  503: 'The server is unavailable right now.',
}

function toApiError(status, payload) {
  const detail = payload?.detail ?? payload
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return new ApiError(detail.message || FALLBACK_MESSAGES[status] || 'Request failed', {
      status, code: detail.code ?? null, data: detail,
    })
  }
  if (Array.isArray(detail)) {
    // FastAPI validation errors
    const msg = detail.map((d) => d.msg).filter(Boolean).join('; ')
    return new ApiError(msg || FALLBACK_MESSAGES[422], { status, code: 'validation_error', data: detail })
  }
  return new ApiError(typeof detail === 'string' && detail ? detail : FALLBACK_MESSAGES[status] || 'Request failed', { status })
}

function authHeaders() {
  const token = getStoredToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function notifyAuthExpired(status) {
  if (status === 401 && getStoredToken()) {
    window.dispatchEvent(new CustomEvent('ciq:auth-expired'))
  }
}

async function request(path, { method = 'GET', body, signal, query } = {}) {
  let url = `${BASE}${path}`
  if (query) {
    const params = new URLSearchParams()
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') params.set(k, v)
    })
    const qs = params.toString()
    if (qs) url += `?${qs}`
  }
  let res
  try {
    res = await fetch(url, {
      method,
      signal,
      headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...authHeaders() },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError(FALLBACK_MESSAGES[0], { status: 0, code: 'network_error' })
  }
  const payload = await res.json().catch(() => null)
  if (!res.ok) {
    notifyAuthExpired(res.status)
    throw toApiError(res.status, payload)
  }
  return payload
}

/** Parse a text/event-stream body, invoking onEvent(name, data) per event. */
async function readEventStream(body, onEvent) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      let event = 'message'
      const data = []
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data.push(line.slice(5).trim())
      }
      if (data.length) {
        try {
          onEvent(event, JSON.parse(data.join('\n')))
        } catch {
          /* ignore malformed event */
        }
      }
    }
  }
}

export const api = {
  signup: (email, username, password) => request('/auth/signup', { method: 'POST', body: { email, username, password } }),
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),
  me: () => request('/auth/me'),
  quota: () => request('/auth/quota'),

  listSessions: ({ limit = 30, offset = 0, q } = {}, signal) => request('/sessions', { query: { limit, offset, q }, signal }),
  getSessionMessages: (id, signal) => request(`/sessions/${encodeURIComponent(id)}/messages`, { signal }),
  renameSession: (id, title) => request(`/sessions/${encodeURIComponent(id)}`, { method: 'PATCH', body: { title } }),
  deleteSession: (id) => request(`/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  /**
   * Ask with live pipeline progress. Resolves with the final result object.
   * `onStatus({stage, ...})` fires for each stage (route, routed, sql, query, answer).
   */
  async ask(question, sessionId, { onStatus, signal } = {}) {
    let res
    try {
      res = await fetch(`${BASE}/ask/stream`, {
        method: 'POST',
        signal,
        headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream', ...authHeaders() },
        body: JSON.stringify({ question, session_id: sessionId }),
      })
    } catch (err) {
      if (err.name === 'AbortError') throw err
      throw new ApiError(FALLBACK_MESSAGES[0], { status: 0, code: 'network_error' })
    }
    if (!res.ok) {
      const payload = await res.json().catch(() => null)
      notifyAuthExpired(res.status)
      throw toApiError(res.status, payload)
    }
    if (!res.body) {
      return request('/ask', { method: 'POST', body: { question, session_id: sessionId }, signal })
    }
    let result = null
    let streamError = null
    await readEventStream(res.body, (event, data) => {
      if (event === 'status') onStatus?.(data)
      else if (event === 'result') result = data
      else if (event === 'error') streamError = data
    })
    if (result) return result
    if (streamError) throw new ApiError(streamError.message, { status: 500, code: streamError.code })
    throw new ApiError('The connection closed before the answer arrived. It may still appear in your history.', {
      code: 'stream_interrupted',
    })
  },

  admin: {
    overview: (days) => request('/admin/overview', { query: { days } }),
    system: () => request('/admin/system'),
    users: (params) => request('/admin/users', { query: params }),
    user: (id) => request(`/admin/users/${id}`),
    updateUser: (id, body) => request(`/admin/users/${id}`, { method: 'PATCH', body }),
    activity: (params) => request('/admin/activity', { query: params }),
  },
}
