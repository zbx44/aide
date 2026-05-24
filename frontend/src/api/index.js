import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

// ===== 对话 =====
export const chat = (message, conversationId = null, userId = 'default') =>
  api.post('/chat', { message, conversation_id: conversationId, stream: false, user_id: userId })

export const chatStream = (message, conversationId = null, userId = 'default', fileContexts = null, kbIds = null) =>
  fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      stream: true,
      user_id: userId,
      file_contexts: fileContexts,
      kb_ids: kbIds,
    }),
  })

export const uploadFiles = (files) => {
  const formData = new FormData()
  for (const f of files) {
    formData.append('files', f)
  }
  return api.post('/chat/upload', formData, {
    timeout: 60000,
    // 不要手动设Content-Type，让浏览器自动设置含boundary的multipart头
  })
}

export const getConversations = () => api.get('/chat/conversations')
export const getMessages = (id) => api.get(`/chat/conversations/${id}/messages`)
export const deleteConversation = (id) => api.delete(`/chat/conversations/${id}`)
export const summarizeConversation = (id) => api.post(`/chat/conversations/${id}/summarize`)

// ===== 记忆 =====
export const searchMemory = (q, category = null) =>
  api.get('/chat/memory/search', { params: { q, category } })
export const listLongTermMemory = (category = null) =>
  api.get('/chat/memory/long-term', { params: { category } })
export const deleteLongTermMemory = (id) =>
  api.delete(`/chat/memory/long-term/${id}`)

// ===== 进化 =====
export const getEvolveStatus = () => api.get('/chat/evolve/status')
export const getEvolveLogs = (type = null) =>
  api.get('/chat/evolve/logs', { params: { type } })
export const manualEvolve = (instruction) =>
  api.post('/chat/evolve', { instruction })

// ===== Skill =====
export const getSkills = (userId = 'default') =>
  api.get('/chat/skills', { params: { user_id: userId } })
export const getAllSkills = () => api.get('/chat/skills/all')
export const getSkill = (name) => api.get(`/chat/skills/${name}`)
export const createSkill = (data) => api.post('/chat/skills', data)
export const deleteSkill = (name) => api.delete(`/chat/skills/${name}`)

// ===== 对话摘要 =====
export const getSummary = (id) => api.get(`/chat/conversations/${id}/summarize`)

// ===== 文档 =====
export const createDoc = (description, docType = 'docx') =>
  api.post('/doc/create', { description, doc_type: docType })

export const modifyDoc = (docId, instruction) =>
  api.post(`/doc/${docId}/modify`, { instruction })

export const downloadDoc = (docId) =>
  `/api/doc/${docId}/download`

export const listDocs = () => api.get('/doc/list')
export const previewDoc = (docId) => api.get(`/doc/${docId}/preview`)
export const deleteDoc = (docId) => api.delete(`/doc/${docId}`)

// ===== 任务 =====
export const listTasks = () => api.get('/task/list')
export const createTask = (configYaml) => api.post('/task/create', { config_yaml: configYaml })
export const runTask = (taskName) => api.post('/task/run', { task_name: taskName })
export const deleteTask = (taskName) => api.delete(`/task/${taskName}`)

// ===== OA =====
export const startOAProcess = (data) => api.post('/oa/start-process', data)
export const uploadOAAttachment = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/oa/upload', formData)
}
export const sendNotify = (data) => api.post('/oa/notify', data)

// ===== 知识库 =====
export const listKnowledgeBases = () => api.get('/kb/list')
export const searchKnowledgeBase = (kbId, q) => api.get(`/${kbId}/search`, { params: { q } })

// ===== 数据源 =====
export const listDatasources = () => api.get('/settings/datasource')
export const addDatasource = (data) => api.post('/settings/datasource', data)
export const updateDatasource = (id, data) => api.put(`/settings/datasource/${id}`, data)
export const deleteDatasource = (id) => api.delete(`/settings/datasource/${id}`)
export const testDatasource = (id) => api.post(`/settings/datasource/${id}/test`)

// ===== 工具 =====
export const listTools = () => api.get('/tool/list')
export const ocrRecognize = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/tool/ocr', formData)
}

export default api
