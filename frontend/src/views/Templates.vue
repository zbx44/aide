<template>
  <div class="templates-page">
    <div class="templates-container">
      <!-- 标题和操作 -->
      <div class="page-header">
        <h1>📝 文档中心</h1>
        <el-button type="primary" @click="showCreateDialog = true">＋ 新建模板</el-button>
      </div>

      <!-- 分类筛选 -->
      <div class="category-filter">
        <el-radio-group v-model="selectedCategory" @change="loadTemplates">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</el-radio-button>
        </el-radio-group>
      </div>

      <!-- 模板卡片 -->
      <div class="template-grid">
        <div
          v-for="tmpl in templates"
          :key="tmpl.name"
          class="template-card"
          :class="'scope-' + tmpl.scope"
          @click="openTemplate(tmpl)"
        >
          <div class="card-icon">{{ tmpl.icon }}</div>
          <div class="card-info">
            <div class="card-name">{{ tmpl.name }}</div>
            <div class="card-desc">{{ tmpl.description }}</div>
            <div class="card-meta">
              <el-tag size="small" :type="tmpl.doc_type === 'docx' ? '' : tmpl.doc_type === 'xlsx' ? 'success' : 'warning'">
                {{ tmpl.doc_type.toUpperCase() }}
              </el-tag>
              <el-tag size="small" type="info">{{ tmpl.scope === 'system' ? '系统' : '个人' }}</el-tag>
              <el-tag size="small" type="warning">{{ tmpl.category }}</el-tag>
            </div>
          </div>
          <div class="card-actions" @click.stop>
            <el-button size="small" type="primary" @click="openTemplate(tmpl)">使用</el-button>
            <el-button v-if="tmpl.scope === 'personal'" size="small" type="danger" @click="deleteTemplate(tmpl.name)">删除</el-button>
          </div>
        </div>

        <el-empty v-if="!templates.length" description="暂无模板" />
      </div>
    </div>

    <!-- 使用模板弹窗 -->
    <el-dialog v-model="showFillDialog" :title="'📊 ' + currentTemplate?.name" width="500px">
      <div class="fill-form">
        <el-form label-width="120px">
          <el-form-item
            v-for="var_def in currentTemplate?.variables || []"
            :key="var_def.name"
            :label="var_def.label"
            :required="var_def.required"
          >
            <!-- 文本输入 -->
            <el-input
              v-if="var_def.type === 'text'"
              v-model="fillVars[var_def.name]"
              :placeholder="'请输入' + var_def.label"
            />

            <!-- 月份选择 -->
            <el-input
              v-else-if="var_def.type === 'month'"
              v-model="fillVars[var_def.name]"
              :placeholder="'如：2026年5月'"
            />

            <!-- 日期 -->
            <el-input
              v-else-if="var_def.type === 'date'"
              v-model="fillVars[var_def.name]"
              :placeholder="'如：今天'"
            />

            <!-- 下拉选择 -->
            <el-select
              v-else-if="var_def.type === 'select'"
              v-model="fillVars[var_def.name]"
            >
              <el-option
                v-for="opt in var_def.options || []"
                :key="opt"
                :value="opt"
                :label="opt"
              />
            </el-select>

            <!-- SQL自动填充 -->
            <div v-else-if="var_def.type === 'sql_query' && var_def.auto_fill" class="auto-fill-hint">
              <el-tag type="success" size="small">🔄 自动从数据库获取</el-tag>
            </div>

            <!-- 其他 -->
            <el-input v-else v-model="fillVars[var_def.name]" />

            <div v-if="var_def.type === 'sql_query' && var_def.auto_fill" class="var-hint">
              💡 数据将自动从数据库获取，无需手动填写
            </div>
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="showFillDialog = false">取消</el-button>
        <el-button type="primary" @click="generateDoc" :loading="generating">
          🚀 生成报告
        </el-button>
      </template>
    </el-dialog>

    <!-- 创建模板弹窗 -->
    <el-dialog v-model="showCreateDialog" title="创建自定义模板" width="500px">
      <el-form label-width="100px">
        <el-form-item label="模板名称" required>
          <el-input v-model="newTemplate.name" placeholder="如：我的周报" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="newTemplate.description" placeholder="模板用途说明" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="newTemplate.category" placeholder="如：设备管理" />
        </el-form-item>
        <el-form-item label="文档类型">
          <el-radio-group v-model="newTemplate.doc_type">
            <el-radio value="docx">Word</el-radio>
            <el-radio value="xlsx">Excel</el-radio>
            <el-radio value="pptx">PPT</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="AI提示词">
          <el-input
            v-model="newTemplate.ai_prompt"
            type="textarea"
            :rows="4"
            placeholder="描述AI应该如何生成文档内容，可用{{变量名}}引用变量"
          />
        </el-form-item>
        <el-form-item label="上传模板文件">
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".docx,.xlsx,.pptx"
            @change="onTemplateFileChange"
          >
            <el-button size="small">选择文件</el-button>
          </el-upload>
          <div class="upload-hint">可选：上传Word/Excel/PPT模板文件</div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTemplate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 生成结果 -->
    <el-dialog v-model="showResultDialog" :title="generatedResult?.status === 'error' ? '生成失败' : '生成完成'" width="400px">
      <div class="result-content">
        <div class="result-icon">{{ generatedResult?.status === 'error' ? '❌' : '✅' }}</div>
        <h3>{{ generatedResult?.title || '未知错误' }}</h3>
        <p v-if="generatedResult?.status !== 'error'">文档已生成，点击下方按钮下载。</p>
        <p v-else style="color: #f56c6c;">{{ generatedResult?.error || '请稍后重试' }}</p>
      </div>
      <template #footer>
        <el-button @click="showResultDialog = false">关闭</el-button>
        <el-button v-if="generatedResult?.status !== 'error'" type="primary" @click="downloadDoc">📥 下载文档</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '../api'

export default {
  name: 'Templates',
  data() {
    return {
      templates: [],
      categories: [],
      selectedCategory: '',
      showFillDialog: false,
      showCreateDialog: false,
      showResultDialog: false,
      currentTemplate: null,
      fillVars: {},
      generating: false,
      generatedResult: null,
      newTemplate: {
        name: '',
        description: '',
        category: '其他',
        doc_type: 'docx',
        ai_prompt: '',
        icon: '📄',
      },
      templateFile: null,
    }
  },
  async mounted() {
    await this.loadTemplates()
    await this.loadCategories()
  },
  methods: {
    async loadTemplates() {
      try {
        const { data } = await api.get('/template/list', {
          params: { category: this.selectedCategory || undefined }
        })
        this.templates = data.templates || []
      } catch (e) {
        console.error('加载模板失败', e)
      }
    },
    async loadCategories() {
      try {
        const { data } = await api.get('/template/categories/list')
        this.categories = data.categories || []
      } catch (e) {
        console.error('加载分类失败', e)
      }
    },
    openTemplate(tmpl) {
      this.currentTemplate = tmpl
      this.fillVars = {}
      // 填入默认值
      for (const v of tmpl.variables || []) {
        if (v.default) this.fillVars[v.name] = v.default
      }
      this.showFillDialog = true
    },
    async generateDoc() {
      if (!this.currentTemplate) return
      this.generating = true
      try {
        const { data } = await api.post('/template/generate', {
          template_name: this.currentTemplate.name,
          variables: this.fillVars,
        })
        if (data.error) {
          this.$message.error('生成失败: ' + data.error)
        } else {
          this.generatedResult = data
          this.showFillDialog = false
          this.showResultDialog = true
          this.$message.success('文档生成成功！')
        }
      } catch (e) {
        const detail = e.response?.data?.detail || e.message || '未知错误'
        this.$message.error('生成失败: ' + detail)
      } finally {
        this.generating = false
      }
    },
    downloadDoc() {
      if (!this.generatedResult) return
      window.open(`/api/doc/${this.generatedResult.doc_id}/download`, '_blank')
    },
    onTemplateFileChange(file) {
      this.templateFile = file.raw
    },
    async createTemplate() {
      if (!this.newTemplate.name) {
        this.$message.warning('请输入模板名称')
        return
      }
      try {
        await api.post('/template/create', this.newTemplate)
        // 如果有模板文件，上传
        if (this.templateFile) {
          const formData = new FormData()
          formData.append('file', this.templateFile)
          await api.post(`/template/${this.newTemplate.name}/upload-template-file`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
          })
        }
        this.$message.success('模板创建成功')
        this.showCreateDialog = false
        this.newTemplate = { name: '', description: '', category: '其他', doc_type: 'docx', ai_prompt: '', icon: '📄' }
        this.templateFile = null
        await this.loadTemplates()
        await this.loadCategories()
      } catch (e) {
        this.$message.error('创建失败: ' + (e.response?.data?.detail || '未知错误'))
      }
    },
    async deleteTemplate(name) {
      try {
        await this.$confirm('确定删除此模板？', '确认', { type: 'warning' })
        await api.delete(`/template/${name}`)
        this.$message.success('已删除')
        await this.loadTemplates()
      } catch (e) {
        if (e !== 'cancel') {
          this.$message.error('删除失败')
        }
      }
    },
  },
}
</script>

<style scoped>
.templates-page {
  padding: 20px;
  overflow-y: auto;
  height: 100vh;
  background: #f5f5f5;
}
.templates-container {
  max-width: 1000px;
  margin: 0 auto;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h1 { margin: 0; font-size: 22px; }
.category-filter { margin-bottom: 20px; }
.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}
.template-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #e4e7ed;
  display: flex;
  gap: 16px;
}
.template-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
  transform: translateY(-2px);
}
.template-card.scope-system { border-left: 3px solid #409eff; }
.template-card.scope-personal { border-left: 3px solid #67c23a; }
.card-icon { font-size: 36px; flex-shrink: 0; }
.card-info { flex: 1; min-width: 0; }
.card-name { font-weight: 600; font-size: 15px; margin-bottom: 4px; }
.card-desc { font-size: 13px; color: #999; margin-bottom: 8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.card-meta { display: flex; gap: 4px; flex-wrap: wrap; }
.card-actions { display: flex; flex-direction: column; gap: 4px; justify-content: center; }
.auto-fill-hint { padding: 4px 0; }
.var-hint { font-size: 12px; color: #999; margin-top: 4px; }
.fill-form { max-height: 60vh; overflow-y: auto; }
.result-content { text-align: center; padding: 20px; }
.result-icon { font-size: 48px; margin-bottom: 12px; }
.upload-hint { font-size: 12px; color: #999; margin-top: 4px; }
</style>
