<template>
  <div class="query-page">
    <!-- 查询方式切换 -->
    <div class="query-tabs">
      <el-radio-group v-model="queryMode" size="large">
        <el-radio-button value="natural">💬 自然语言</el-radio-button>
        <el-radio-button value="sql">💻 SQL查询</el-radio-button>
        <el-radio-button value="visual">🔧 可视化构建</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 数据源选择 -->
    <div class="ds-selector" v-if="datasources.length">
      <el-select v-model="selectedDsId" placeholder="选择 数据源" size="small" style="width: 260px" clearable>
        <el-option v-for="ds in datasourceOptions" :key="ds.id" :label="`${typeLabel(ds.type)} ${ds.name}`" :value="ds.id">
          <span>{{ typeLabel(ds.type) }} {{ ds.name }}</span>
          <span style="float: right; color: #909399; font-size: 11px">{{ ds.type === 'sqlite' ? ds.database : ds.host }}</span>
        </el-option>
      </el-select>
    </div>

    <!-- 自然语言模式 -->
    <div v-if="queryMode === 'natural'" class="query-section">
      <div class="natural-input">
        <el-input
          v-model="naturalQuestion"
          type="textarea"
          :rows="3"
          placeholder="用自然语言描述你想查的数据，例如：查一下本月故障率最高的5台设备"
          @keydown.enter.ctrl="executeNatural"
        />
        <el-button type="primary" @click="executeNatural" :loading="loading" size="large">
          🔍 查询
        </el-button>
      </div>
      <div class="quick-examples">
        <span class="examples-label">试试：</span>
        <el-tag
          v-for="ex in examples"
          :key="ex"
          @click="naturalQuestion = ex; executeNatural()"
          class="example-tag"
          effect="plain"
        >
          {{ ex }}
        </el-tag>
      </div>
    </div>

    <!-- SQL模式 -->
    <div v-if="queryMode === 'sql'" class="query-section">
      <el-input
        v-model="sqlText"
        type="textarea"
        :rows="6"
        placeholder="输入SELECT查询语句..."
        @keydown.enter.ctrl="executeSQL"
      />
      <div class="sql-actions">
        <el-button type="primary" @click="executeSQL" :loading="loading">
          ▶ 执行
        </el-button>
        <span class="sql-hint">Ctrl+Enter执行 | 只允许SELECT查询</span>
      </div>
    </div>

    <!-- 可视化构建模式 -->
    <div v-if="queryMode === 'visual'" class="query-section">
      <el-form label-width="80px">
        <el-form-item label="数据表">
          <el-select v-model="visualQuery.table_name" placeholder="选择数据表" @change="onTableChange">
            <el-option
              v-for="t in schemaTables"
              :key="t.name"
              :label="`${t.name}（${t.comment}）`"
              :value="t.name"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="显示字段">
          <el-checkbox-group v-model="visualQuery.columns">
            <el-checkbox
              v-for="col in currentTableColumns"
              :key="col.name"
              :value="col.name"
              :label="col.name"
            >
              {{ col.name }}（{{ col.comment }}）
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="筛选条件">
          <div v-for="(cond, idx) in visualQuery.conditions" :key="idx" class="condition-row">
            <el-select v-model="cond.field" placeholder="字段" style="width: 150px">
              <el-option v-for="col in currentTableColumns" :key="col.name" :value="col.name" :label="col.name" />
            </el-select>
            <el-select v-model="cond.op" style="width: 110px">
              <el-option value="=" label="等于" />
              <el-option value="!=" label="不等于" />
              <el-option value=">" label="大于" />
              <el-option value=">=" label="大于等于" />
              <el-option value="<" label="小于" />
              <el-option value="<=" label="小于等于" />
              <el-option value="LIKE" label="包含" />
            </el-select>
            <el-input v-model="cond.value" placeholder="值" style="width: 200px" />
            <el-button type="danger" circle size="small" @click="removeCondition(idx)">✕</el-button>
          </div>
          <el-button size="small" @click="addCondition">＋ 添加条件</el-button>
        </el-form-item>

        <el-form-item label="排序">
          <el-select v-model="visualQuery.order_by" placeholder="排序字段" clearable style="width: 180px">
            <el-option v-for="col in currentTableColumns" :key="col.name" :value="col.name" :label="col.name" />
          </el-select>
          <el-radio-group v-model="visualQuery.order_dir" style="margin-left: 12px">
            <el-radio value="ASC">升序</el-radio>
            <el-radio value="DESC">降序</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="限制条数">
          <el-input-number v-model="visualQuery.limit" :min="1" :max="5000" :step="10" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="executeVisual" :loading="loading">🔍 查询</el-button>
          <el-button @click="saveAsTask">📋 保存为定时任务</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 查询结果展示 -->
    <div v-if="result" class="result-section">
      <!-- SQL展示（自然语言和可视化模式） -->
      <div v-if="result.sql && queryMode !== 'sql'" class="sql-display">
        <el-collapse>
          <el-collapse-item title="📝 生成的SQL">
            <code>{{ result.sql }}</code>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- 错误信息 -->
      <el-alert v-if="result.error" type="error" :closable="false" style="margin-bottom: 16px;">
        {{ result.error }}
      </el-alert>

      <!-- AI解读 -->
      <div v-if="result.interpretation" class="interpretation">
        <h4>💡 AI解读</h4>
        <div v-html="renderMarkdown(result.interpretation)"></div>
      </div>

      <!-- 数据表格 -->
      <div v-if="result.columns && result.columns.length" class="data-table">
        <div class="table-header">
          <span>📊 查询结果（{{ result.total }} 条）</span>
          <el-button size="small" @click="exportCSV">📥 导出CSV</el-button>
        </div>
        <el-table :data="result.rows" stripe border size="small" max-height="400"
                  :default-sort="{prop: result.columns[0], order: 'descending'}">
          <el-table-column v-for="col in result.columns" :key="col" :prop="col" :label="col"
                           sortable show-overflow-tooltip />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script>
import MarkdownIt from 'markdown-it'
import api from '../api'

const md = new MarkdownIt()

export default {
  name: 'Query',
  data() {
    return {
      queryMode: 'natural',
      loading: false,
      result: null,
      // 数据源
      datasources: [],
      selectedDsId: '',
      // 自然语言
      naturalQuestion: '',
      examples: [
        '查一下本月故障率最高的5台设备',
        '3号车间上周的维修记录',
        '库存低于最低存量的备件',
        '最近30天的巡检异常记录',
      ],
      // SQL
      sqlText: '',
      // 可视化
      schemaTables: [],
      visualQuery: {
        table_name: '',
        columns: [],
        conditions: [],
        order_by: '',
        order_dir: 'DESC',
        limit: 100,
      },
    }
  },
  computed: {
    currentTableColumns() {
      if (!this.visualQuery.table_name) return []
      const table = this.schemaTables.find(t => t.name === this.visualQuery.table_name)
      return table ? table.columns : []
    },
    datasourceOptions() {
      return this.datasources.filter(ds => ds.enabled)
    },
  },
  async mounted() {
    await this.loadDatasources()
    await this.loadSchema()
  },
  methods: {
    renderMarkdown(text) {
      return md.render(text || '')
    },

    typeLabel(type) {
      const map = { dm: '🗄️', mysql: '🐬', postgresql: '🐘', sqlite: '📄' }
      return map[type] || '💾'
    },

    async loadDatasources() {
      try {
        const { data } = await api.get('/settings/datasource')
        this.datasources = data.datasources || []
        // 默认选第一个启用的
        if (!this.selectedDsId && this.datasourceOptions.length) {
          this.selectedDsId = this.datasourceOptions[0].id
        }
      } catch (e) {
        console.error('加载数据源失败', e)
      }
    },

    async loadSchema() {
      try {
        const { data } = await api.get('/query/schema')
        this.schemaTables = data.tables || []
      } catch (e) {
        console.error('加载Schema失败', e)
      }
    },

    onTableChange() {
      this.visualQuery.columns = []
      this.visualQuery.conditions = []
    },

    addCondition() {
      this.visualQuery.conditions.push({ field: '', op: '=', value: '' })
    },

    removeCondition(idx) {
      this.visualQuery.conditions.splice(idx, 1)
    },

    async executeNatural() {
      if (!this.naturalQuestion.trim()) return
      this.loading = true
      this.result = null
      try {
        const { data } = await api.post('/query/natural', { question: this.naturalQuestion, datasource_id: this.selectedDsId || undefined })
        this.result = data
      } catch (e) {
        this.result = { error: e.response?.data?.detail || '查询失败' }
      } finally {
        this.loading = false
      }
    },

    async executeSQL() {
      if (!this.sqlText.trim()) return
      this.loading = true
      this.result = null
      try {
        const { data } = await api.post('/query/sql', { sql: this.sqlText, datasource_id: this.selectedDsId || undefined })
        this.result = data
      } catch (e) {
        this.result = { error: e.response?.data?.detail || 'SQL执行失败' }
      } finally {
        this.loading = false
      }
    },

    async executeVisual() {
      if (!this.visualQuery.table_name) return
      this.loading = true
      this.result = null
      try {
        const payload = { ...this.visualQuery, datasource_id: this.selectedDsId || undefined }
        const { data } = await api.post('/query/visual', payload)
        this.result = data
      } catch (e) {
        this.result = { error: e.response?.data?.detail || '查询失败' }
      } finally {
        this.loading = false
      }
    },

    saveAsTask() {
      // 跳转到任务页面预填
      this.$router.push('/task')
    },

    exportCSV() {
      if (!this.result || !this.result.columns) return
      const rows = [this.result.columns.join(','), ...this.result.rows.map(r => r.join(','))]
      const csv = rows.join('\n')
      const BOM = '\uFEFF'
      const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `query_result_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    },
  },
}
</script>

<style scoped>
.query-page {
  padding: 20px;
  overflow-y: auto;
  height: 100vh;
  background: #f5f5f5;
}
.query-tabs {
  margin-bottom: 12px;
}
.ds-selector {
  margin-bottom: 16px;
  padding: 8px 12px;
  background: #fff;
  border-radius: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.ds-selector::before {
  content: '数据源：';
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}
.query-section {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
}
.natural-input {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.natural-input .el-textarea { flex: 1; }
.quick-examples {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.examples-label { font-size: 13px; color: #999; }
.example-tag { cursor: pointer; }
.sql-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}
.sql-hint { font-size: 12px; color: #999; }
.condition-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.result-section {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
}
.sql-display { margin-bottom: 16px; }
.sql-display code {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  display: block;
  font-size: 13px;
  white-space: pre-wrap;
}
.interpretation {
  margin-bottom: 16px;
  padding: 16px;
  background: #f0f9eb;
  border-radius: 8px;
  border-left: 3px solid #67c23a;
}
.interpretation h4 { margin: 0 0 8px; font-size: 15px; }
.data-table { margin-top: 16px; }
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-weight: 600;
}
</style>
