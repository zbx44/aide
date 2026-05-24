<template>
  <div class="chat-page">
    <!-- 欢迎引导 -->
    <WelcomeGuide ref="welcomeGuide" @try-example="onTryExample" />

    <!-- 渐进提示 -->
    <FeatureTip tip-id="first-upload" text="你可以上传文件让我分析，试试点击上传按钮" position="bottom-right" />

    <!-- 对话列表 -->
    <div class="conversation-list" v-if="showSidebar">
      <el-button type="primary" size="small" @click="newConversation" style="margin: 10px;">
        新对话
      </el-button>
      <div
        v-for="conv in conversations"
        :key="conv.conversation_id"
        class="conv-item"
        :class="{ active: conv.conversation_id === currentConvId }"
        @click="selectConversation(conv.conversation_id)"
      >
        <span class="conv-title">{{ conv.last_message || '新对话' }}</span>
        <span class="conv-time">{{ formatTime(conv.last_at) }}</span>
        <span class="conv-delete" @click.stop="deleteConversation(conv.conversation_id)" title="删除对话"><el-icon><Delete /></el-icon></span>
      </div>
    </div>

    <!-- 聊天区域 -->
    <div class="chat-area">
      <!-- 快捷按钮 -->
      <QuickActions @prefill="onPrefill" />

      <div class="messages" ref="messagesRef">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message"
          :class="msg.role"
        >
          <div class="msg-bubble">
            <!-- 用户消息附件标记 -->
            <div v-if="msg.files && msg.files.length" class="msg-files">
              <span v-for="f in msg.files" :key="f.filename" class="msg-file-tag">
                {{ fileIcon(f.type) }} {{ f.filename }}
              </span>
            </div>
            <!-- 工具调用展示 -->
            <div v-if="msg.tool_calls && msg.tool_calls.length" class="tool-calls">
              <div v-for="tc in msg.tool_calls" :key="tc.name" class="tool-call-item">
                <el-tag size="small" type="warning">🔧 {{ tc.name }}</el-tag>
                <span class="tool-args">{{ JSON.stringify(tc.arguments) }}</span>
                <span v-if="tc.result" class="tool-result">
                  <template v-if="tc.result.error">❌ {{ tc.result.error }}</template>
                  <template v-else>✅ 执行成功</template>
                </span>
              </div>
            </div>
            <div v-html="renderMarkdown(msg.content)"></div>
            <!-- 思考过程展示 -->
            <div v-if="msg.thinking" class="thinking-block" @click="toggleThinking(msg.id)">
              <div class="thinking-header">
                <span>💭 思考过程</span>
                <span class="thinking-toggle">{{ expandedThinking[msg.id] ? '▼' : '▶' }}</span>
              </div>
              <div v-if="expandedThinking[msg.id]" class="thinking-content" v-html="renderMarkdown(msg.thinking)"></div>
            </div>
          </div>
        </div>
        <div v-if="streaming" class="message assistant">
          <div class="msg-bubble streaming">
            <div v-if="streamToolInfo" class="tool-calls">
              <el-tag size="small" type="warning">{{ streamToolInfo }}</el-tag>
            </div>
            <div v-if="streamThinking" class="thinking-block" @click="toggleStreamThinking">
              <div class="thinking-header">
                <span>💭 思考过程</span>
                <span class="thinking-toggle">{{ showStreamThinking ? '▼' : '▶' }}</span>
              </div>
              <div v-if="showStreamThinking" class="thinking-content" v-html="renderMarkdown(streamThinking)"></div>
            </div>
            <div v-html="renderMarkdown(streamContent)"></div>
            <span class="cursor">▊</span>
          </div>
        </div>
      </div>

      <!-- 输入框 -->
      <div class="input-area">
        <!-- 顶部快捷栏 -->
        <div class="input-toolbar">
          <el-button size="small" text @click="showSkillPanel = true" title="可用技能">
            <el-icon><SetUp /></el-icon> 技能
          </el-button>
          <el-button size="small" text @click="showMemoryPanel = true" title="记忆">
            <el-icon><Cpu /></el-icon> 记忆
          </el-button>
          <el-button size="small" text @click="showEvolvePanel = true" title="自我进化">
            <el-icon><MagicStick /></el-icon> 进化
          </el-button>
          <div style="flex:1"></div>
          <el-select
            v-model="selectedKbIds"
            multiple
            collapse-tags
            collapse-tags-tooltip
            :placeholder="knowledgeBases.length ? '选择知识库增强回答' : '暂无知识库'"
            size="small"
            style="width: 240px"
            clearable
            :disabled="!knowledgeBases.length"
          >
            <el-option
              v-for="kb in knowledgeBases"
              :key="kb.id"
              :label="kb.name"
              :value="kb.id"
            >
              <span>{{ kb.name }}</span>
              <span style="float: right; color: var(--el-text-color-secondary); font-size: 12px">{{ kb.doc_count || 0 }}篇</span>
            </el-option>
          </el-select>
        </div>
        <!-- 输入框 + 附件 + 发送 -->
        <div class="input-box">
          <!-- 已上传附件预览 -->
          <div class="file-preview" v-if="uploadedFiles.length">
            <div v-for="(f, idx) in uploadedFiles" :key="idx" class="file-chip">
              <span class="file-icon">{{ fileIcon(f.type) }}</span>
              <span class="file-name" :title="f.filename">{{ f.filename }}</span>
              <el-button link size="small" @click="removeFile(idx)">✕</el-button>
            </div>
          </div>
          <div class="input-row-bottom">
            <el-input
              v-model="inputText"
              type="textarea"
              :rows="2"
              :autosize="{ minRows: 2, maxRows: 6 }"
              placeholder="输入消息..."
              @keydown.enter.exact="sendMessage"
              resize="none"
            />
            <div class="input-side">
              <el-button text circle @click="triggerUpload" title="添加附件" :loading="uploading">
                <el-icon :size="20"><Paperclip /></el-icon>
              </el-button>
              <input
                ref="fileInput"
                type="file"
                multiple
                accept=".docx,.xlsx,.pptx,.pdf,.png,.jpg,.jpeg,.gif,.bmp,.webp,.txt,.md,.csv,.json,.yaml,.yml"
                style="display: none"
                @change="handleFileSelect"
              />
              <el-button type="primary" circle @click="sendMessage" :loading="loading" title="发送">
                <el-icon :size="20"><Promotion /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Skill面板 -->
    <el-drawer v-model="showSkillPanel" title="可用技能" direction="rtl" size="380px">
      <div class="skill-level-info">
        <el-tag :type="levelTagType">{{ levelInfo.current_level_label }}</el-tag>
        <span class="level-progress">{{ levelInfo.next_level_requirement }}</span>
      </div>
      <div class="skills-grid">
        <div v-for="skill in visibleSkills" :key="skill.name" class="skill-card"
             :class="'level-' + skill.level">
          <div class="skill-header">
            <span class="skill-name">{{ skill.display_name }}</span>
            <el-tag size="small" :type="skill.level === 1 ? 'success' : skill.level === 2 ? 'warning' : 'danger'">
              L{{ skill.level }}
            </el-tag>
          </div>
          <p class="skill-desc">{{ skill.description }}</p>
          <div class="skill-meta">
            <span class="skill-category">{{ skill.category }}</span>
            <span class="skill-usage">使用 {{ skill.usage_count }} 次</span>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- 记忆面板 -->
    <el-drawer v-model="showMemoryPanel" title="记忆" direction="rtl" size="420px">
      <el-tabs>
        <el-tab-pane label="长期记忆">
          <el-input v-model="memorySearchQuery" placeholder="搜索记忆..." @input="searchMemory" clearable>
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <div class="memory-list">
            <div v-for="mem in memoryResults" :key="mem.id" class="memory-item">
              <el-tag size="small" :type="memoryTagType(mem.category)">{{ mem.category }}</el-tag>
              <span class="memory-content">{{ mem.content }}</span>
              <span class="memory-importance">重要度: {{ mem.importance?.toFixed(1) }}</span>
            </div>
            <el-empty v-if="!memoryResults.length" description="暂无长期记忆" />
          </div>
        </el-tab-pane>
        <el-tab-pane label="对话摘要">
          <div v-if="currentSummary" class="summary-content">
            <p>{{ currentSummary.summary }}</p>
            <div v-if="currentSummary.key_topics" class="key-topics">
              <el-tag v-for="topic in parseTopics(currentSummary.key_topics)" :key="topic" size="small" style="margin: 2px;">{{ topic }}</el-tag>
            </div>
          </div>
          <el-empty v-else description="暂无摘要" />
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

    <!-- 进化面板 -->
    <el-drawer v-model="showEvolvePanel" title="自我进化" direction="rtl" size="420px">
      <div class="evolve-status">
        <el-descriptions :column="2" size="small" border>
          <el-descriptions-item label="Prompt版本">v{{ evolveStatus.prompt_version }}</el-descriptions-item>
          <el-descriptions-item label="学到的规则">{{ evolveStatus.learned_rules_count }}条</el-descriptions-item>
          <el-descriptions-item label="人格特质">{{ (evolveStatus.personality_traits || []).join('、') }}</el-descriptions-item>
          <el-descriptions-item label="下次反思">第{{ evolveStatus.next_reflection_at }}轮</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="evolve-action">
        <el-input v-model="evolveInstruction" type="textarea" :rows="2"
                  placeholder="输入改进指令，如：回答更简洁、记住我喜欢表格格式..." />
        <el-button type="primary" @click="triggerEvolve" :loading="evolving" style="margin-top: 8px;">
          <el-icon><MagicStick /></el-icon> 执行进化
        </el-button>
      </div>

      <h4 style="margin-top: 16px;">进化日志</h4>
      <el-timeline>
        <el-timeline-item v-for="log in evolveLogs" :key="log.id"
                          :timestamp="formatTime(log.created_at)" placement="top">
          <el-tag size="small" :type="evolveTagType(log.type)">{{ log.type }}</el-tag>
          <p class="evolve-content">{{ truncate(log.content, 100) }}</p>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!evolveLogs.length" description="暂无进化记录" />
    </el-drawer>
  </div>
</template>

<script>
import { chatStream, getConversations, getMessages, searchMemory, getSummary, uploadFiles, listKnowledgeBases, deleteConversation, listLongTermMemory } from '../api'
import {
  getSkills, getEvolveStatus, getEvolveLogs, manualEvolve
} from '../api'
import MarkdownIt from 'markdown-it'
import WelcomeGuide from '../components/WelcomeGuide.vue'
import QuickActions from '../components/QuickActions.vue'
import FeatureTip from '../components/FeatureTip.vue'

const md = new MarkdownIt()

export default {
  name: 'Chat',
  components: { WelcomeGuide, QuickActions, FeatureTip },
  data() {
    return {
      conversations: [],
      currentConvId: null,
      messages: [],
      inputText: '',
      loading: false,
      streaming: false,
      streamContent: '',
      streamThinking: '',
      showStreamThinking: true,
      streamToolInfo: '',
      expandedThinking: {},
      showSidebar: true,
      // File upload
      uploadedFiles: [],
      uploading: false,
      // Skill
      showSkillPanel: false,
      visibleSkills: [],
      levelInfo: {},
      // Memory
      showMemoryPanel: false,
      memorySearchQuery: '',
      memoryResults: [],
      currentSummary: null,
      // Evolution
      showEvolvePanel: false,
      evolveStatus: {},
      evolveLogs: [],
      // Knowledge Base
      knowledgeBases: [],
      selectedKbIds: [],
      evolveInstruction: '',
      evolving: false,
    }
  },
  computed: {
    levelTagType() {
      return this.levelInfo.current_level === 1 ? 'success'
        : this.levelInfo.current_level === 2 ? 'warning' : 'danger'
    }
    },
  async mounted() {
    await this.loadConversations()
    await this.loadKnowledgeBases()
  },
  beforeDestroy() {
    // 组件销毁前确保清理状态，防止卡死
    this.streaming = false
    this.loading = false
  },
  methods: {
    renderMarkdown(text) {
      return md.render(text || '')
    },
    formatTime(isoStr) {
      if (!isoStr) return ''
      try {
        const d = new Date(isoStr)
        return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`
      } catch { return '' }
    },
    truncate(str, len) {
      if (!str) return ''
      return str.length > len ? str.slice(0, len) + '...' : str
    },
    parseTopics(topics) {
      if (Array.isArray(topics)) return topics
      try { return JSON.parse(topics) } catch { return [] }
    },
    memoryTagType(cat) {
      return { fact: '', preference: 'success', rule: 'warning', lesson: 'danger' }[cat] || 'info'
    },
    evolveTagType(type) {
      return { reflection: 'info', learning: 'success', prompt_update: 'warning', skill_update: '' }[type] || 'info'
    },
    toggleThinking(msgId) {
      this.expandedThinking[msgId] = !this.expandedThinking[msgId]
    },
    toggleStreamThinking() {
      this.showStreamThinking = !this.showStreamThinking
    },

    // ===== 欢迎引导 & 快捷操作 =====
    onTryExample(text) {
      this.inputText = text
      this.$nextTick(() => this.sendMessage())
    },
    onPrefill(prefix) {
      this.inputText = prefix
      this.$refs?.inputText?.focus()
    },

    // ===== 文件上传 =====
    triggerUpload() {
      this.$refs.fileInput.click()
    },
    async handleFileSelect(e) {
      const files = e.target.files
      if (!files || !files.length) return

      this.uploading = true
      try {
        const { data } = await uploadFiles(Array.from(files))
        for (const f of data.files) {
          if (f.error) {
            this.$message.warning(`${f.filename}: ${f.error}`)
          } else {
            this.uploadedFiles.push(f)
          }
        }
        if (this.uploadedFiles.length) {
          this.$message.success(`已添加 ${this.uploadedFiles.length} 个文件`)
        }
      } catch (err) {
        this.$message.error('文件上传失败: ' + (err.message || '未知错误'))
      } finally {
        this.uploading = false
        // 清空input，允许再次选择同名文件
        e.target.value = ''
      }
    },
    removeFile(idx) {
      this.uploadedFiles.splice(idx, 1)
    },
    fileIcon(type) {
      const icons = {
        word: '📄', excel: '📊', ppt: '📑',
        pdf: '📕', image: '🖼️', text: '📝',
        unsupported: '❓', error: '⚠️'
      }
      return icons[type] || '📎'
    },

    // ===== 对话 =====
    async loadConversations() {
      try {
        const { data } = await getConversations()
        this.conversations = data
      } catch (e) { console.error(e) }
    },
    async loadKnowledgeBases() {
      try {
        const { data } = await listKnowledgeBases()
        this.knowledgeBases = data.kbs || data || []
      } catch (e) { console.error(e) }
    },
    newConversation() {
      this.currentConvId = null
      this.messages = []
      this.currentSummary = null
    },
    async selectConversation(id) {
      this.currentConvId = id
      try {
        const { data } = await getMessages(id)
        this.messages = data.map(m => {
          const msg = { id: m.id, role: m.role, content: m.content }
          // Extract thinking from metadata
          if (m.metadata) {
            try {
              const meta = typeof m.metadata === 'string' ? JSON.parse(m.metadata) : m.metadata
              if (meta.thinking) msg.thinking = meta.thinking
              if (meta.tool_calls) msg.tool_calls = meta.tool_calls
            } catch {}
          }
          return msg
        })
        this.$nextTick(() => this.scrollToBottom())
        this.loadSummary(id)
      } catch (e) { console.error(e) }
    },
    async deleteConversation(id) {
      try {
        await this.$confirm('确定删除这个对话？删除后不可恢复。', '确认删除', {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteConversation(id)
        if (this.currentConvId === id) {
          this.currentConvId = null
          this.messages = []
          this.currentSummary = null
        }
        this.loadConversations()
        this.$message.success('已删除')
      } catch (e) {
        if (e !== 'cancel') this.$message.error('删除失败')
      }
    },
    async loadSummary(id) {
      try {
        const { data } = await getSummary(id)
        this.currentSummary = data
      } catch { this.currentSummary = null }
    },
    async sendMessage(e) {
      if (e && e.shiftKey) return
      if (e) e.preventDefault()

      const text = this.inputText.trim()
      if (!text || this.loading) return

      const fileContexts = this.uploadedFiles.length ? this.uploadedFiles.map(f => ({
        filename: f.filename,
        type: f.type,
        text: f.text,
        image_base64: f.image_base64,
        media_type: f.media_type,
      })) : null

      this.messages.push({
        id: Date.now(),
        role: 'user',
        content: text,
        files: this.uploadedFiles.length ? this.uploadedFiles.map(f => ({ filename: f.filename, type: f.type })) : undefined,
      })
      this.inputText = ''
      this.uploadedFiles = []
      this.loading = true
      this.streaming = true
      this.streamContent = ''
      this.streamThinking = ''
      this.showStreamThinking = true
      this.streamToolInfo = ''

      try {
        const response = await chatStream(text, this.currentConvId, undefined, fileContexts, this.selectedKbIds.length ? this.selectedKbIds : null)

        // 先检查HTTP状态码，非200直接走错误处理
        if (!response.ok) {
          let errMsg = `请求失败: HTTP ${response.status}`
          try {
            const errBody = await response.text()
            const errParsed = JSON.parse(errBody)
            errMsg = errParsed.detail || errParsed.error?.message || errMsg
          } catch {}
          throw new Error(errMsg)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let timeoutId = null

        // 超时保护：60秒没收到任何数据自动结束
        const resetTimeout = () => {
          if (timeoutId) clearTimeout(timeoutId)
          timeoutId = setTimeout(() => {
            if (this.streaming) {
              console.warn('SSE流超时，自动关闭')
              if (this.streamContent || this.streamThinking) {
                this.messages.push({
                  id: Date.now(),
                  role: 'assistant',
                  content: this.streamContent || '（响应超时，内容不完整）',
                  thinking: this.streamThinking || undefined,
                  tool_calls: [],
                })
              }
              this.streaming = false
              this.loading = false
              this.streamContent = ''
              this.streamThinking = ''
              this.streamToolInfo = ''
              this.loadConversations()
            }
          }, 60000)
        }
        resetTimeout()

        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            resetTimeout()
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() || ''

            for (const line of lines) {
              if (line.startsWith('data:')) {
                const raw = line.slice(5).trim()
                if (!raw) continue
                try {
                  const parsed = JSON.parse(raw)
                  if (parsed.type === 'tool_calls') {
                    this.streamToolInfo = parsed.tools
                  } else if (parsed.type === 'thinking') {
                    this.streamThinking += parsed.text
                  } else if (parsed.type === 'content') {
                    this.streamContent += parsed.text
                  } else if (parsed.type === 'error') {
                    this.streamContent = parsed.text
                    // 收到错误，立即结束流
                    this.streaming = false
                  } else if (parsed.type === 'done') {
                    if (parsed.conversation_id && !this.currentConvId) {
                      this.currentConvId = parsed.conversation_id
                    }
                    this.streaming = false
                  }
                } catch {
                  // 非JSON格式，拼接为内容
                  this.streamContent += raw
                }
              }
              if (line.startsWith('event:done')) {
                this.streaming = false
              }
            }

            // 流已结束，保存消息
            if (!this.streaming) {
              if (this.streamContent || this.streamThinking) {
                this.messages.push({
                  id: Date.now(),
                  role: 'assistant',
                  content: this.streamContent || '（无内容）',
                  thinking: this.streamThinking || undefined,
                  tool_calls: [],
                })
              }
              this.streamContent = ''
              this.streamThinking = ''
              this.streamToolInfo = ''
              break
            }

            this.$nextTick(() => this.scrollToBottom())
          }
        } finally {
          if (timeoutId) clearTimeout(timeoutId)
          // 确保reader被释放
          try { reader.releaseLock() } catch {}
        }

        // 如果循环结束但streaming还在（理论上 shouldn't happen）
        if (this.streaming) {
          if (this.streamContent || this.streamThinking) {
            this.messages.push({
              id: Date.now(),
              role: 'assistant',
              content: this.streamContent,
              thinking: this.streamThinking || undefined,
              tool_calls: [],
            })
          }
          this.streaming = false
          this.streamContent = ''
          this.streamThinking = ''
        }

        await this.loadConversations()
      } catch (e) {
        console.error(e)
        // 确保错误时彻底清理状态
        if (this.streaming) {
          this.messages.push({
            id: Date.now(),
            role: 'assistant',
            content: `错误: ${e.message}`,
          })
        }
        this.streaming = false
        this.streamContent = ''
        this.streamThinking = ''
        this.streamToolInfo = ''
        // 错误后也刷新对话列表
        this.loadConversations().catch(() => {})
      } finally {
        this.loading = false
        this.$nextTick(() => this.scrollToBottom())
      }
    },
    scrollToBottom() {
      const el = this.$refs.messagesRef
      if (el) el.scrollTop = el.scrollHeight
    },

    // ===== Skill =====
    async loadSkills() {
      try {
        const { data } = await getSkills()
        this.visibleSkills = data.skills || []
        this.levelInfo = {
          ...data.level_info,
          current_level_label: `Level ${data.level_info?.current_level || 1}`,
        }
      } catch (e) { console.error(e) }
    },

    // ===== Memory =====
    async searchMemory() {
      try {
        if (this.memorySearchQuery) {
          const { data } = await searchMemory(this.memorySearchQuery)
          this.memoryResults = data
        } else {
          const { data } = await listLongTermMemory()
          this.memoryResults = data.memories || data || []
        }
      } catch (e) { console.error(e); this.memoryResults = [] }
    },

    // ===== Evolution =====
    async loadEvolveStatus() {
      try {
        const { data } = await getEvolveStatus()
        this.evolveStatus = data
      } catch (e) { console.error(e) }
    },
    async loadEvolveLogs() {
      try {
        const { data } = await getEvolveLogs()
        this.evolveLogs = data
      } catch (e) { console.error(e) }
    },
    async triggerEvolve() {
      if (!this.evolveInstruction.trim()) return
      this.evolving = true
      try {
        const { data } = await manualEvolve(this.evolveInstruction)
        this.$message.success('进化完成！' + (data.explanation || ''))
        this.evolveInstruction = ''
        await this.loadEvolveStatus()
        await this.loadEvolveLogs()
      } catch (e) {
        this.$message.error('进化失败: ' + e.message)
      } finally {
        this.evolving = false
      }
    },
  },
  watch: {
    showSkillPanel(v) { if (v) this.loadSkills() },
    showMemoryPanel(v) { if (v) { this.searchMemory(); if (this.currentConvId) this.loadSummary(this.currentConvId) } },
    showEvolvePanel(v) { if (v) { this.loadEvolveStatus(); this.loadEvolveLogs() } },
  },
}
</script>

<style scoped>
.chat-page {
  display: flex;
  height: 100vh;
}
.conversation-list {
  width: 220px;
  background: #f5f5f5;
  border-right: 1px solid #ddd;
  overflow-y: auto;
}
.conv-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #eee;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 6px;
}
.conv-item:hover { background: #e8e8e8; }
.conv-item.active { background: #ddd; }
.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
}
.conv-time {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
}
.conv-delete {
  display: none;
  cursor: pointer;
  font-size: 14px;
  flex-shrink: 0;
  opacity: 0.6;
}
.conv-delete:hover { opacity: 1; }
.conv-item:hover .conv-delete { display: inline; }
.conv-item:hover .conv-time { display: none; }
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.message {
  margin-bottom: 16px;
  display: flex;
}
.message.user { justify-content: flex-end; }
.message.assistant { justify-content: flex-start; }
.msg-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  font-size: 14px;
}
.message.user .msg-bubble {
  background: #409eff;
  color: white;
}
.message.assistant .msg-bubble {
  background: #f0f0f0;
  color: #333;
}
.streaming .cursor {
  animation: blink 1s infinite;
}
@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}
.input-area {
  display: flex;
  flex-direction: column;
  padding: 8px 12px 12px;
  gap: 6px;
  border-top: 1px solid #ddd;
  background: #fff;
}
.input-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
}
.input-toolbar .el-button { padding: 4px 8px; }
.input-box {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.input-box:focus-within {
  border-color: #409eff;
}
.input-row-bottom {
  display: flex;
  align-items: flex-end;
  gap: 0;
}
.input-row-bottom .el-textarea {
  flex: 1;
}
.input-row-bottom .el-textarea :deep(.el-textarea__inner) {
  border: none !important;
  box-shadow: none !important;
  padding: 10px 12px;
  background: transparent;
  resize: none;
}
.input-side {
  display: flex;
  flex-direction: row;
  align-items: flex-end;
  gap: 4px;
  padding: 6px 8px;
}
.send-bar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 4px;
}
.send-hint {
  font-size: 12px;
  color: #999;
}

/* File upload */
.file-preview {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.file-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
  border-radius: 16px;
  font-size: 12px;
  max-width: 200px;
}
.file-chip .file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-chip .file-icon { font-size: 14px; }

/* Message file tags */
.msg-files {
  margin-bottom: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.msg-file-tag {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px 8px;
  background: rgba(255,255,255,0.2);
  border-radius: 10px;
  font-size: 11px;
}

/* Tool Calls */
.tool-calls {
  margin-bottom: 8px;
  padding: 8px;
  background: rgba(230, 162, 60, 0.1);
  border-radius: 6px;
  border: 1px solid #e6a23c;
}
.tool-call-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 4px 0;
  font-size: 12px;
}
.tool-args {
  color: #666;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-result { font-size: 12px; }

/* Thinking Block */
.thinking-block {
  margin-bottom: 10px;
  border: 1px solid #c0c4cc;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
}
.thinking-block:hover {
  border-color: #909399;
}
.thinking-header {
  padding: 8px 12px;
  background: #f5f7fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #606266;
  user-select: none;
}
.thinking-toggle {
  font-size: 11px;
  color: #909399;
}
.thinking-content {
  padding: 10px 12px;
  font-size: 13px;
  color: #606266;
  background: #fafafa;
  border-top: 1px solid #ebeef5;
  max-height: 400px;
  overflow-y: auto;
  line-height: 1.6;
}

/* Skill Cards */
.skill-level-info {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.level-progress { font-size: 12px; color: #999; }
.skills-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.skill-card {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  background: #fafafa;
}
.skill-card.level-1 { border-left: 3px solid #67c23a; }
.skill-card.level-2 { border-left: 3px solid #e6a23c; }
.skill-card.level-3 { border-left: 3px solid #f56c6c; }
.skill-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.skill-name { font-weight: 600; }
.skill-desc { font-size: 13px; color: #666; margin: 4px 0; }
.skill-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #999;
}

/* Memory */
.memory-list { margin-top: 12px; }
.memory-item {
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  background: #f5f5f5;
  font-size: 13px;
}
.memory-content { display: block; margin: 4px 0; }
.memory-importance { font-size: 11px; color: #999; }
.summary-content { padding: 12px; background: #f5f5f5; border-radius: 8px; }
.key-topics { margin-top: 8px; }

/* Evolution */
.evolve-status { margin-bottom: 16px; }
.evolve-action { margin: 16px 0; }
.evolve-content { font-size: 13px; margin-top: 4px; }
</style>
