<template>
  <div class="settings-page">
    <div class="settings-container">
      <h1><el-icon><Setting /></el-icon> 系统设置</h1>

      <!-- LLM Provider切换 -->
      <el-card class="setting-card">
        <template #header>
          <div class="card-header">
            <span><el-icon><Cpu /></el-icon> 大模型配置</span>
            <el-tag :type="llmStatus.thinking_model ? 'warning' : 'success'" size="small">
              {{ llmStatus.thinking_model ? '思考模式' : '普通模式' }}
            </el-tag>
          </div>
        </template>

        <el-form label-width="120px">
          <el-form-item label="当前Provider">
            <el-radio-group v-model="selectedProvider" @change="switchProvider">
              <el-radio-button value="vllm"><el-icon><Monitor /></el-icon> 本地vLLM</el-radio-button>
              <el-radio-button value="tencent"><el-icon><Cloudy /></el-icon> 腾讯混元</el-radio-button>
              <el-radio-button value="openai"><el-icon><Connection /></el-icon> OpenAI兼容</el-radio-button>
              <el-radio-button value="custom"><el-icon><SetUp /></el-icon> 自定义</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="当前状态">
            <el-descriptions :column="2" size="small" border>
              <el-descriptions-item label="Provider">{{ llmStatus.provider }}</el-descriptions-item>
              <el-descriptions-item label="模型">{{ llmStatus.model }}</el-descriptions-item>
              <el-descriptions-item label="API地址">{{ llmStatus.base_url }}</el-descriptions-item>
              <el-descriptions-item label="思考模式">
                <el-switch v-model="thinkingOverride" @change="toggleThinking" active-text="开" inactive-text="关" />
              </el-descriptions-item>
              <el-descriptions-item label="工具调用">
                <el-tag :type="llmStatus.supports_tools ? 'success' : 'info'" size="small">
                  {{ llmStatus.supports_tools ? '支持' : '不支持' }}
                </el-tag>
              </el-descriptions-item>
            </el-descriptions>
          </el-form-item>

          <el-form-item label="最大Token数">
            <el-input-number v-model="llmForm.max_tokens" :min="256" :max="32768" :step="256" />
          </el-form-item>

          <el-form-item label="温度">
            <el-slider v-model="llmForm.temperature" :min="0" :max="2" :step="0.1" :format-tooltip="v => v.toFixed(1)" style="width: 300px" />
          </el-form-item>
        </el-form>

        <el-collapse v-model="expandedProviders" class="provider-config">
          <el-collapse-item title="<el-icon><Monitor /></el-icon> 本地vLLM" name="vllm">
            <el-form label-width="120px" size="small">
              <el-form-item label="API地址"><el-input v-model="providerConfigs.vllm.base_url" placeholder="http://localhost:8000/v1" /></el-form-item>
              <el-form-item label="API Key"><el-input v-model="providerConfigs.vllm.api_key" placeholder="本地部署通常不需要" /></el-form-item>
              <el-form-item label="模型名"><el-input v-model="providerConfigs.vllm.model" placeholder="qwen3.6-27B" /></el-form-item>
            </el-form>
          </el-collapse-item>
          <el-collapse-item title="<el-icon><Cloudy /></el-icon> 腾讯混元" name="tencent">
            <el-form label-width="120px" size="small">
              <el-form-item label="API地址"><el-input v-model="providerConfigs.tencent.base_url" placeholder="https://api.lkeap.cloud.tencent.com/plan/v3" /></el-form-item>
              <el-form-item label="API Key"><el-input v-model="providerConfigs.tencent.api_key" type="password" show-password /></el-form-item>
              <el-form-item label="模型名">
                <el-select v-model="providerConfigs.tencent.model" filterable allow-create>
                  <el-option value="glm-5.1" label="GLM-5.1 (深度思考)" />
                  <el-option value="hunyuan-lite" label="hunyuan-lite (免费)" />
                  <el-option value="deepseek-v4-flash" label="DeepSeek-V4-Flash" />
                </el-select>
              </el-form-item>
            </el-form>
          </el-collapse-item>
          <el-collapse-item title="<el-icon><Connection /></el-icon> OpenAI兼容" name="openai">
            <el-form label-width="120px" size="small">
              <el-form-item label="API地址"><el-input v-model="providerConfigs.openai.base_url" placeholder="https://api.deepseek.com/v1" /></el-form-item>
              <el-form-item label="API Key"><el-input v-model="providerConfigs.openai.api_key" type="password" show-password /></el-form-item>
              <el-form-item label="模型名"><el-input v-model="providerConfigs.openai.model" placeholder="deepseek-chat" /></el-form-item>
            </el-form>
          </el-collapse-item>
          <el-collapse-item title="<el-icon><SetUp /></el-icon> 自定义" name="custom">
            <el-form label-width="120px" size="small">
              <el-form-item label="API地址"><el-input v-model="providerConfigs.custom.base_url" /></el-form-item>
              <el-form-item label="API Key"><el-input v-model="providerConfigs.custom.api_key" type="password" show-password /></el-form-item>
              <el-form-item label="模型名"><el-input v-model="providerConfigs.custom.model" /></el-form-item>
            </el-form>
          </el-collapse-item>
        </el-collapse>
        <div style="margin-top: 16px; text-align: right;">
          <el-button type="primary" @click="saveAllProviderConfigs" :loading="saving">保存所有配置</el-button>
        </div>
      </el-card>

      <!-- 数据源配置 -->
      <el-card class="setting-card" style="margin-top: 16px;">
        <template #header>
          <div class="card-header">
            <span><el-icon><Coin /></el-icon> 数据源配置</span>
            <el-button type="primary" size="small" @click="showAddDsDialog()">＋ 添加数据源</el-button>
          </div>
        </template>

        <el-table :data="datasources" stripe border size="small" style="width: 100%">
          <el-table-column prop="name" label="名称" width="160" />
          <el-table-column prop="type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ typeLabel(row.type) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="连接地址" min-width="200">
            <template #default="{ row }">
              {{ row.type === 'sqlite' ? row.database : `${row.host}:${row.port}` }}
            </template>
          </el-table-column>
          <el-table-column prop="database" label="数据库" width="120" />
          <el-table-column prop="enabled" label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="toggleDs(row)" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center">
            <template #default="{ row }">
              <el-button size="small" @click="testDs(row)" :loading="testingDsId === row.id">测试</el-button>
              <el-button size="small" @click="editDs(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="removeDs(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-empty v-if="!datasources.length" description="暂无数据源，请点击右上角添加" />
      </el-card>

      <!-- 数据源 编辑对话框 -->
      <el-dialog v-model="dsDialogVisible" :title="dsForm.id ? '编辑数据源' : '添加数据源'" width="520px">
        <el-form :model="dsForm" label-width="100px" size="small">
          <el-form-item label="名称" required>
            <el-input v-model="dsForm.name" placeholder="如：达梦主库、MySQL测试库" />
          </el-form-item>
          <el-form-item label="类型" required>
            <el-select v-model="dsForm.type" @change="onDsTypeChange">
              <el-option value="dm" label="🗄️ 达梦数据库" />
              <el-option value="mysql" label="🐬 MySQL" />
              <el-option value="postgresql" label="🐘 PostgreSQL" />
              <el-option value="sqlite" label="<el-icon><Document /></el-icon> SQLite" />
            </el-select>
          </el-form-item>

          <template v-if="dsForm.type !== 'sqlite'">
            <el-form-item label="主机地址" required>
              <el-input v-model="dsForm.host" placeholder="127.0.0.1" />
            </el-form-item>
            <el-form-item v-if="dsForm.type === 'dm'" label="备库地址">
              <el-input v-model="dsForm.standby_host" placeholder="127.0.0.2" />
            </el-form-item>
            <el-form-item label="端口">
              <el-input-number v-model="dsForm.port" :min="1" :max="65535" />
            </el-form-item>
            <el-form-item label="用户名"><el-input v-model="dsForm.username" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="dsForm.password" type="password" show-password /></el-form-item>
            <el-form-item label="数据库名"><el-input v-model="dsForm.database" placeholder="lczx" /></el-form-item>
          </template>

          <template v-else>
            <el-form-item label="数据库文件"><el-input v-model="dsForm.database" placeholder="D:/data/my.db" /></el-form-item>
          </template>

          <el-form-item label="启用">
            <el-switch v-model="dsForm.enabled" />
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="dsDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveDsForm" :loading="savingDs">保存</el-button>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Settings',
  data() {
    return {
      // LLM
      selectedProvider: 'vllm',
      llmStatus: {},
      thinkingOverride: false,
      llmForm: { max_tokens: 4096, temperature: 0.7 },
      providerConfigs: {
        vllm: { base_url: '', api_key: '', model: '' },
        tencent: { base_url: 'https://api.lkeap.cloud.tencent.com/plan/v3', api_key: '', model: 'glm-5.1' },
        openai: { base_url: '', api_key: '', model: '' },
        custom: { base_url: '', api_key: '', model: '' },
      },
      expandedProviders: [],
      saving: false,

      // 数据源
      datasources: [],
      dsDialogVisible: false,
      dsForm: { id: '', name: '', type: 'dm', host: '', standby_host: '', port: 5236, username: '', password: '', database: '', enabled: true },
      savingDs: false,
      testingDsId: '',
    }
  },
  async mounted() {
    await this.loadLLMStatus()
    await this.loadDatasources()
  },
  methods: {
    typeLabel(type) {
      const map = { dm: '达梦', mysql: 'MySQL', postgresql: 'PostgreSQL', sqlite: 'SQLite' }
      return map[type] || type
    },

    // ===== LLM =====
    async loadLLMStatus() {
      try {
        const resp = await fetch('/api/chat/llm/status')
        this.llmStatus = await resp.json()
        this.selectedProvider = this.llmStatus.provider || 'vllm'
        this.thinkingOverride = this.llmStatus.thinking_model || false
        this.llmForm.max_tokens = this.llmStatus.max_tokens || 4096
        this.llmForm.temperature = this.llmStatus.temperature || 0.7
      } catch (e) { console.error(e) }
    },
    async switchProvider(provider) {
      try {
        const resp = await fetch('/api/chat/llm/switch', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider }),
        })
        if (!resp.ok) { const err = await resp.json(); this.$message.error(err.detail || '切换失败'); this.selectedProvider = this.llmStatus.provider; return }
        const data = await resp.json()
        this.llmStatus = data
        this.thinkingOverride = data.thinking_model || false
        this.$message.success(`已切换到 ${provider}`)
      } catch (e) { this.$message.error('切换失败'); this.selectedProvider = this.llmStatus.provider }
    },
    async toggleThinking(val) {
      try {
        await fetch('/api/chat/llm/switch', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ provider: this.selectedProvider, thinking_model: val }),
        })
        this.$message.success(`思考模式已${val ? '开启' : '关闭'}`)
        await this.loadLLMStatus()
      } catch (e) { this.$message.error('设置失败') }
    },
    async saveAllProviderConfigs() {
      this.saving = true
      try {
        for (const [provider, config] of Object.entries(this.providerConfigs)) {
          if (!config.base_url && !config.api_key && !config.model) continue
          await fetch('/api/chat/llm/config', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider, ...config }),
          })
        }
        this.$message.success('LLM配置已保存，重启后生效')
      } catch (e) { this.$message.error('保存失败') }
      finally { this.saving = false }
    },

    // ===== 数据源 =====
    async loadDatasources() {
      try {
        const resp = await fetch('/api/settings/datasource')
        const data = await resp.json()
        this.datasources = data.datasources || []
      } catch (e) { console.error(e) }
    },

    getDefaultPort(type) {
      const map = { dm: 5236, mysql: 3306, postgresql: 5432, sqlite: 0 }
      return map[type] || 0
    },

    onDsTypeChange(type) {
      this.dsForm.port = this.getDefaultPort(type)
      if (type === 'sqlite') {
        this.dsForm.host = ''
        this.dsForm.username = ''
        this.dsForm.password = ''
      }
    },

    showAddDsDialog() {
      this.dsForm = { id: '', name: '', type: 'dm', host: '', standby_host: '', port: 5236, username: '', password: '', database: '', enabled: true }
      this.dsDialogVisible = true
    },

    editDs(row) {
      this.dsForm = { ...row, password: row.password || '' }
      this.dsDialogVisible = true
    },

    async saveDsForm() {
      if (!this.dsForm.name) { this.$message.warning('请填写名称'); return }
      this.savingDs = true
      try {
        if (this.dsForm.id) {
          // 更新
          await fetch(`/api/settings/datasource/${this.dsForm.id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.dsForm),
          })
          this.$message.success('更新成功')
        } else {
          // 添加
          await fetch('/api/settings/datasource', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.dsForm),
          })
          this.$message.success('添加成功')
        }
        this.dsDialogVisible = false
        await this.loadDatasources()
      } catch (e) { this.$message.error('保存失败') }
      finally { this.savingDs = false }
    },

    async toggleDs(row) {
      try {
        await fetch(`/api/settings/datasource/${row.id}`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: row.enabled }),
        })
      } catch (e) { this.$message.error('更新失败') }
    },

    async testDs(row) {
      this.testingDsId = row.id
      try {
        const resp = await fetch(`/api/settings/datasource/${row.id}/test`, { method: 'POST' })
        const data = await resp.json()
        if (data.success) { this.$message.success(data.message) }
        else { this.$message.error(data.message) }
      } catch (e) { this.$message.error('测试失败') }
      finally { this.testingDsId = '' }
    },

    async removeDs(row) {
      try {
        await this.$confirm(`确定删除数据源"${row.name}"？`, '确认', { type: 'warning' })
        await fetch(`/api/settings/datasource/${row.id}`, { method: 'DELETE' })
        this.$message.success('已删除')
        await this.loadDatasources()
      } catch (e) { if (e !== 'cancel') this.$message.error('删除失败') }
    },
  },
}
</script>

<style scoped>
.settings-page { height: 100vh; overflow-y: auto; background: #f0f2f5; }
.settings-container { max-width: 960px; margin: 0 auto; padding: 24px; }
.settings-container h1 { margin: 0 0 20px 0; font-size: 24px; }
.setting-card { border-radius: 12px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.provider-config { margin-top: 16px; }
</style>
