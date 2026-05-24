<template>
  <div class="kb-page">
    <div class="kb-header">
      <h2>📚 知识库</h2>
      <el-button type="primary" @click="showCreateDialog = true">创建知识库</el-button>
    </div>

    <!-- 知识库列表 -->
    <div class="kb-grid" v-if="!currentKb">
      <el-card v-for="kb in knowledgeBases" :key="kb.id" class="kb-card" shadow="hover"
               @click="selectKb(kb.id)">
        <template #header>
          <div class="kb-card-header">
            <span class="kb-name">📁 {{ kb.name }}</span>
            <el-dropdown @command="handleKbCommand($event, kb.id)" @click.stop>
              <span class="el-dropdown-link">⋯</span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="delete" style="color:#f56c6c">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </template>
        <p class="kb-desc">{{ kb.description || '暂无描述' }}</p>
        <div class="kb-stats">
          <el-tag size="small">{{ kb.doc_count }} 文档</el-tag>
          <el-tag size="small" type="info">{{ kb.chunk_count }} 分块</el-tag>
        </div>
      </el-card>
      <el-empty v-if="!knowledgeBases.length" description="暂无知识库，点击上方创建" />
    </div>

    <!-- 知识库详情 -->
    <div v-if="currentKb" class="kb-detail">
      <el-page-header @back="currentKb = null; currentKbDetail = null" :content="currentKbDetail?.name" />
      
      <div class="kb-detail-actions">
        <el-upload :action="`/api/kb/${currentKb}/upload`" :on-success="onUploadSuccess"
                   :on-error="onUploadError" :show-file-list="false"
                   accept=".docx,.xlsx,.pptx,.pdf,.md,.txt,.csv,.json,.yaml,.yml">
          <el-button type="success">📤 上传文档</el-button>
        </el-upload>
        <el-button @click="showSearchDialog = true">🔍 检索测试</el-button>
      </div>

      <p v-if="currentKbDetail?.description" class="kb-detail-desc">{{ currentKbDetail.description }}</p>

      <!-- 文档列表 -->
      <el-table :data="currentDocs" style="margin-top: 16px;">
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="file_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块" width="80" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'ready' ? 'success' : row.status === 'error' ? 'danger' : 'warning'">
              {{ row.status === 'ready' ? '✅' : row.status === 'error' ? '❌' : '⏳' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="deleteDoc(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 创建知识库对话框 -->
    <el-dialog v-model="showCreateDialog" title="创建知识库" width="400px">
      <el-form :model="newKb" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newKb.name" placeholder="如：产品文档库" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newKb.description" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createKb">创建</el-button>
      </template>
    </el-dialog>

    <!-- 检索测试对话框 -->
    <el-dialog v-model="showSearchDialog" title="检索测试" width="600px">
      <el-input v-model="searchQuery" placeholder="输入搜索关键词...">
        <template #append>
          <el-button @click="doSearch" :loading="searching">搜索</el-button>
        </template>
      </el-input>
      <div class="search-results" v-if="searchResults.length">
        <div v-for="(r, i) in searchResults" :key="i" class="search-result-item">
          <div class="result-header">
            <el-tag size="small">分块 #{{ r.chunk_index }}</el-tag>
            <span class="result-score">相关度: {{ (r._score || 0).toFixed(2) }}</span>
          </div>
          <p class="result-content">{{ r.preview || r.content?.slice(0, 300) }}</p>
        </div>
      </div>
      <el-empty v-else-if="searchDone" description="未找到相关内容" />
    </el-dialog>
  </div>
</template>

<script>
import axios from 'axios'
const api = axios.create({ baseURL: '/api', timeout: 120000 })

export default {
  name: 'Knowledge',
  data() {
    return {
      knowledgeBases: [],
      currentKb: null,
      currentKbDetail: null,
      currentDocs: [],
      showCreateDialog: false,
      showSearchDialog: false,
      newKb: { name: '', description: '' },
      searchQuery: '',
      searchResults: [],
      searching: false,
      searchDone: false,
    }
  },
  async mounted() {
    await this.loadKbs()
  },
  methods: {
    formatSize(bytes) {
      if (!bytes) return '-'
      if (bytes < 1024) return bytes + 'B'
      if (bytes < 1048576) return (bytes/1024).toFixed(1) + 'KB'
      return (bytes/1048576).toFixed(1) + 'MB'
    },
    async loadKbs() {
      const { data } = await api.get('/kb/list')
      this.knowledgeBases = data
    },
    async selectKb(id) {
      this.currentKb = id
      const { data } = await api.get(`/kb/${id}`)
      this.currentKbDetail = data
      this.currentDocs = data.documents || []
    },
    async createKb() {
      if (!this.newKb.name.trim()) return
      await api.post('/kb/create', null, { params: this.newKb })
      this.showCreateDialog = false
      this.newKb = { name: '', description: '' }
      await this.loadKbs()
      this.$message.success('知识库创建成功')
    },
    async handleKbCommand(cmd, kbId) {
      if (cmd === 'delete') {
        await this.$confirm('确定删除此知识库及其所有文档？', '警告', { type: 'warning' })
        await api.delete(`/kb/${kbId}`)
        await this.loadKbs()
        this.$message.success('已删除')
      }
    },
    async deleteDoc(docId) {
      await api.delete(`/kb/documents/${docId}`)
      await this.selectKb(this.currentKb)
      this.$message.success('文档已删除')
    },
    onUploadSuccess() {
      this.$message.success('文档上传成功')
      this.selectKb(this.currentKb)
    },
    onUploadError(err) {
      this.$message.error('上传失败: ' + (err.message || '未知错误'))
    },
    async doSearch() {
      if (!this.searchQuery.trim()) return
      this.searching = true
      this.searchDone = false
      try {
        const { data } = await api.get(`/kb/${this.currentKb}/search`, { params: { q: this.searchQuery } })
        this.searchResults = data
        this.searchDone = true
      } catch (e) {
        this.$message.error('检索失败')
      } finally {
        this.searching = false
      }
    },
  },
}
</script>

<style scoped>
.kb-page { padding: 24px; max-width: 1000px; margin: 0 auto; }
.kb-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.kb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
.kb-card { cursor: pointer; }
.kb-card:hover { transform: translateY(-2px); }
.kb-card-header { display: flex; justify-content: space-between; align-items: center; }
.kb-name { font-weight: 600; font-size: 15px; }
.kb-desc { font-size: 13px; color: #666; margin: 8px 0; }
.kb-stats { display: flex; gap: 8px; }
.kb-detail { max-width: 900px; }
.kb-detail-actions { display: flex; gap: 12px; margin-top: 16px; }
.kb-detail-desc { color: #666; font-size: 13px; margin-top: 8px; }
.search-results { margin-top: 16px; }
.search-result-item { padding: 12px; background: #f5f5f5; border-radius: 8px; margin-bottom: 8px; }
.result-header { display: flex; gap: 8px; align-items: center; margin-bottom: 4px; }
.result-score { font-size: 12px; color: #999; }
.result-content { font-size: 13px; line-height: 1.5; }
</style>
