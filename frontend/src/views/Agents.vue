<template>
  <div class="agents-page">
    <div class="agents-container">
      <!-- 标题和操作 -->
      <div class="page-header">
        <h1>🤖 智能体广场</h1>
        <div class="header-actions">
          <el-button @click="showConfigDrawer = true" title="配置FastAGI连接">⚙️ 配置</el-button>
          <el-button @click="showAddDialog = true" type="primary">＋ 添加智能体</el-button>
        </div>
      </div>

      <!-- 分类筛选 -->
      <div class="category-filter" v-if="categories.length > 1">
        <el-radio-group v-model="selectedCategory">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 智能体卡片 -->
      <div class="agent-grid">
        <div
          v-for="agent in filteredAgents"
          :key="agent.id"
          class="agent-card"
          @click="openChat(agent)"
        >
          <div class="card-icon">{{ agent.icon || '🤖' }}</div>
          <div class="card-info">
            <div class="card-name">{{ agent.name }}</div>
            <div class="card-desc">{{ agent.description }}</div>
            <div class="card-meta">
              <el-tag size="small" type="info">{{ agent.category || '通用' }}</el-tag>
              <el-tag v-if="agent.agent_id" size="small" type="success">已接入</el-tag>
              <el-tag v-else size="small" type="danger">未配置</el-tag>
            </div>
          </div>
          <div class="card-actions" @click.stop>
            <el-button size="small" type="primary" @click="openChat(agent)" :disabled="!agent.agent_id">对话</el-button>
            <el-button size="small" @click="editAgent(agent)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteAgent(agent.id)">删除</el-button>
          </div>
        </div>

        <el-empty v-if="!agents.length" description="暂无智能体，点击右上角添加" />
      </div>
    </div>

    <!-- ===== 智能体对话弹窗 ===== -->
    <el-dialog
      v-model="showChatDialog"
      :title="(currentAgent?.icon || '🤖') + ' ' + currentAgent?.name"
      width="700px"
      top="5vh"
      destroy-on-close
    >
      <div class="agent-chat">
        <div class="chat-messages" ref="chatMessagesRef">
          <div
            v-for="msg in chatMessages"
            :key="msg.id"
            class="chat-msg"
            :class="msg.role"
          >
            <div class="msg-bubble">
              <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)"></div>
              <div v-else>{{ msg.content }}</div>
            </div>
          </div>
          <div v-if="chatStreaming" class="chat-msg assistant">
            <div class="msg-bubble streaming">
              <div v-html="renderMarkdown(chatStreamContent)"></div>
              <span class="cursor">▊</span>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <el-input
            v-model="chatInput"
            type="textarea"
            :rows="2"
            placeholder="输入问题，Enter发送..."
            @keydown.enter.exact.prevent="sendAgentChat"
            :disabled="chatLoading"
          />
          <el-button
            type="primary"
            @click="sendAgentChat"
            :loading="chatLoading"
            :disabled="!chatInput.trim()"
          >
            发送
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- ===== 添加/编辑智能体弹窗 ===== -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingAgent ? '编辑智能体' : '添加智能体'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="agentForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="agentForm.name" placeholder="如：法规助手" />
        </el-form-item>
        <el-form-item label="图标">
          <el-input v-model="agentForm.icon" placeholder="如：⚖️" style="width: 80px" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="agentForm.category" placeholder="如：通用、法规、技术" />
        </el-form-item>
        <el-form-item label="简介" required>
          <el-input v-model="agentForm.description" type="textarea" :rows="3" placeholder="描述智能体的功能和适用场景" />
        </el-form-item>
        <el-form-item label="Agent ID" required>
          <el-input v-model="agentForm.agent_id" placeholder="FastAGI中的智能体ID" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="agentForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="saveAgentForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- ===== FastAGI配置抽屉 ===== -->
    <el-drawer v-model="showConfigDrawer" title="⚙️ FastAGI 连接配置" direction="rtl" size="420px">
      <el-form label-width="120px">
        <el-form-item label="API地址">
          <el-input v-model="configForm.base_url" placeholder="https://fastagi-cloud-test.deepexi.com" />
        </el-form-item>
        <el-form-item label="APP_ID">
          <el-input v-model="configForm.app_id" placeholder="应用的APP_ID" />
        </el-form-item>
        <el-form-item label="SECRET_KEY">
          <el-input v-model="configForm.secret_key" type="password" show-password placeholder="应用的SECRET_KEY（用于自动生成签名）" />
          <div style="font-size:12px;color:#909399;margin-top:4px;">SECRET_KEY是固定密钥，每次调用API时会自动用HMAC-SHA256生成动态签名</div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveConfig" :loading="configSaving">保存配置</el-button>
          <el-button @click="reloadAgents">重新加载</el-button>
        </el-form-item>
        <el-form-item label="当前状态">
          <el-tag :type="configInfo.secret_key_set ? 'success' : 'danger'">
            {{ configInfo.secret_key_set ? '已配置' : '未配置' }}
          </el-tag>
          <span style="margin-left: 8px; color: #999">智能体数量: {{ configInfo.agents_count || 0 }}</span>
        </el-form-item>
      </el-form>
      <div style="margin-top: 20px; padding: 12px; background: #f5f7fa; border-radius: 8px;">
        <h4>配置说明</h4>
        <p style="font-size: 13px; color: #666; line-height: 1.6;">
          FastAGI是滴普的大模型工作流平台，类似Dify。<br>
          1. 在FastAGI中创建应用，获取 APP_ID 和 SECRET_KEY<br>
          2. 在此填写连接信息<br>
          3. 添加智能体，填写对应的 agent_id<br>
          配置文件位置：data/agents.json
        </p>
      </div>
    </el-drawer>
  </div>
</template>

<script>
import MarkdownIt from 'markdown-it'
const md = new MarkdownIt()

export default {
  name: 'Agents',
  data() {
    return {
      agents: [],
      selectedCategory: '',
      // 对话
      showChatDialog: false,
      currentAgent: null,
      chatMessages: [],
      chatInput: '',
      chatLoading: false,
      chatStreaming: false,
      chatStreamContent: '',
      chatConversationId: '',
      // 添加/编辑
      showAddDialog: false,
      editingAgent: null,
      agentForm: { name: '', icon: '🤖', category: '通用', description: '', agent_id: '', enabled: true },
      // 配置
      showConfigDrawer: false,
      configForm: { base_url: '', app_id: '', secret_key: '' },
      configInfo: {},
      configSaving: false,
    }
  },
  computed: {
    categories() {
      const cats = new Set(this.agents.map(a => a.category || '通用'))
      return [...cats]
    },
    filteredAgents() {
      if (!this.selectedCategory) return this.agents
      return this.agents.filter(a => (a.category || '通用') === this.selectedCategory)
    },
  },
  async mounted() {
    await this.loadAgents()
    await this.loadConfig()
  },
  methods: {
    renderMarkdown(text) {
      return md.render(text || '')
    },

    // ===== 智能体列表 =====
    async loadAgents() {
      try {
        const { data } = await fetch('/api/agent/list').then(r => r.json())
        this.agents = data.agents || []
      } catch (e) {
        console.error(e)
      }
    },

    openChat(agent) {
      if (!agent.agent_id) {
        this.$message.warning('该智能体尚未配置Agent ID')
        return
      }
      this.currentAgent = agent
      this.chatMessages = []
      this.chatInput = ''
      this.chatConversationId = ''
      this.chatStreaming = false
      this.chatStreamContent = ''
      this.showChatDialog = true
    },

    editAgent(agent) {
      this.editingAgent = agent
      this.agentForm = { ...agent }
      this.showAddDialog = true
    },

    deleteAgent(id) {
      this.$confirm('确定删除该智能体？', '提示', { type: 'warning' }).then(async () => {
        const newAgents = this.agents.filter(a => a.id !== id)
        await fetch('/api/agent/agents/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agents: newAgents }),
        })
        this.$message.success('已删除')
        await this.loadAgents()
      }).catch(() => {})
    },

    async saveAgentForm() {
      if (!this.agentForm.name || !this.agentForm.description) {
        this.$message.warning('请填写名称和简介')
        return
      }
      let agents = [...this.agents]
      if (this.editingAgent) {
        agents = agents.map(a => a.id === this.editingAgent.id ? { ...a, ...this.agentForm } : a)
      } else {
        this.agentForm.id = this.agentForm.id || 'agent_' + Date.now()
        agents.push({ ...this.agentForm })
      }
      await fetch('/api/agent/agents/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agents }),
      })
      this.$message.success('保存成功')
      this.showAddDialog = false
      this.editingAgent = null
      this.agentForm = { name: '', icon: '🤖', category: '通用', description: '', agent_id: '', enabled: true }
      await this.loadAgents()
    },

    // ===== 对话 =====
    async sendAgentChat() {
      const text = this.chatInput.trim()
      if (!text || this.chatLoading) return

      this.chatMessages.push({ id: Date.now(), role: 'user', content: text })
      this.chatInput = ''
      this.chatLoading = true
      this.chatStreaming = true
      this.chatStreamContent = ''

      try {
        const resp = await fetch('/api/agent/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            agent_id: this.currentAgent.id,
            query: text,
            conversation_id: this.chatConversationId,
            user: 'aide',
          }),
        })

        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`)
        }

        const reader = resp.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data:')) {
              const raw = line.slice(5).trim()
              if (!raw) continue
              try {
                const parsed = JSON.parse(raw)
                if (parsed.event === 'error') {
                  this.chatStreamContent = parsed.error || '请求出错'
                } else if (parsed.answer) {
                  this.chatStreamContent += parsed.answer
                }
                if (parsed.conversation_id) {
                  this.chatConversationId = parsed.conversation_id
                }
              } catch {
                this.chatStreamContent += raw
              }
            }
            if (line.startsWith('event:done')) {
              this.chatStreaming = false
            }
          }
          this.$nextTick(() => this.scrollChat())
        }

        // 流结束，保存消息
        if (this.chatStreamContent) {
          this.chatMessages.push({ id: Date.now(), role: 'assistant', content: this.chatStreamContent })
        }
        this.chatStreaming = false
        this.chatStreamContent = ''
      } catch (e) {
        console.error(e)
        this.chatMessages.push({ id: Date.now(), role: 'assistant', content: `错误: ${e.message}` })
        this.chatStreaming = false
      } finally {
        this.chatLoading = false
        this.$nextTick(() => this.scrollChat())
      }
    },

    scrollChat() {
      const el = this.$refs.chatMessagesRef
      if (el) el.scrollTop = el.scrollHeight
    },

    // ===== 配置 =====
    async loadConfig() {
      try {
        this.configInfo = await fetch('/api/agent/config').then(r => r.json())
        this.configForm.base_url = this.configInfo.base_url || ''
        this.configForm.app_id = this.configInfo.app_id || ''
      } catch (e) {
        console.error(e)
      }
    },

    async saveConfig() {
      this.configSaving = true
      try {
        await fetch('/api/agent/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.configForm),
        })
        this.$message.success('配置已保存')
        await this.loadConfig()
        await this.loadAgents()
      } catch (e) {
        this.$message.error('保存失败: ' + e.message)
      } finally {
        this.configSaving = false
      }
    },

    async reloadAgents() {
      try {
        await fetch('/api/agent/reload', { method: 'POST' })
        await this.loadAgents()
        await this.loadConfig()
        this.$message.success('已重新加载')
      } catch (e) {
        this.$message.error('重新加载失败')
      }
    },
  },
}
</script>

<style scoped>
.agents-page { height: 100vh; overflow-y: auto; background: #f0f2f5; }
.agents-container { max-width: 1200px; margin: 0 auto; padding: 24px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h1 { margin: 0; font-size: 24px; }
.header-actions { display: flex; gap: 8px; }
.category-filter { margin-bottom: 20px; }

.agent-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}

.agent-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e4e7ed;
  display: flex;
  gap: 16px;
}
.agent-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); transform: translateY(-2px); }

.card-icon { font-size: 40px; flex-shrink: 0; width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: #f5f7fa; border-radius: 12px; }
.card-info { flex: 1; min-width: 0; }
.card-name { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.card-desc { font-size: 13px; color: #666; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.card-meta { display: flex; gap: 6px; }
.card-actions { display: flex; flex-direction: column; gap: 4px; justify-content: center; }

/* 对话 */
.agent-chat { height: 60vh; display: flex; flex-direction: column; }
.chat-messages { flex: 1; overflow-y: auto; padding: 12px; border: 1px solid #e4e7ed; border-radius: 8px; margin-bottom: 12px; background: #fafafa; }
.chat-msg { margin-bottom: 12px; }
.chat-msg.user { text-align: right; }
.msg-bubble { display: inline-block; max-width: 80%; padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.6; text-align: left; }
.chat-msg.user .msg-bubble { background: #409eff; color: #fff; border-bottom-right-radius: 4px; }
.chat-msg.assistant .msg-bubble { background: #fff; border: 1px solid #e4e7ed; border-bottom-left-radius: 4px; }
.msg-bubble.streaming { border-color: #409eff; }
.cursor { animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: 0; } }

.chat-input { display: flex; gap: 8px; align-items: flex-end; }
.chat-input .el-textarea { flex: 1; }
</style>
