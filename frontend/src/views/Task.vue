<template>
  <div class="task-page" style="padding: 20px;">
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div style="display: flex; justify-content: space-between;">
              <span>📊 定时分析任务</span>
              <el-button type="primary" size="small" @click="showCreateDialog = true">
                新建任务
              </el-button>
            </div>
          </template>
          <el-table :data="tasks" stripe>
            <el-table-column prop="name" label="任务名称" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="schedule" label="调度">
              <template #default="{ row }">
                {{ row.schedule?.cron || row.schedule?.interval + 's' || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="enabled" label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" type="primary" link @click="runTask(row.name)">
                  执行
                </el-button>
                <el-button size="small" type="danger" link @click="deleteTask(row.name)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card>
          <template #header><span>📝 任务说明</span></template>
          <div style="font-size: 13px; line-height: 1.8; color: #666;">
            <p>每个分析任务包含：</p>
            <ul>
              <li><b>调度配置</b>：cron表达式或间隔时间</li>
              <li><b>SQL查询</b>：从达梦数据库取数</li>
              <li><b>分析提示词</b>：告诉AI如何分析</li>
              <li><b>输出模板</b>：报告格式和文件名</li>
              <li><b>通知配置</b>：完成后推送（可选）</li>
            </ul>
            <p>配置使用YAML格式，支持变量替换。</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新建任务对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建分析任务" width="700px">
      <el-input
        v-model="newTaskYaml"
        type="textarea"
        :rows="18"
        placeholder="粘贴任务YAML配置..."
      />
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { listTasks, createTask as apiCreateTask, runTask as apiRunTask, deleteTask as apiDeleteTask } from '../api'

const DEFAULT_YAML = `name: "新任务"
description: "任务描述"
enabled: true

schedule:
  cron: "0 8 * * *"

database:
  host: "127.0.0.1"
  standby: "127.0.0.2"
  port: 5236
  username: "username"
  password: ""
  database: "database"

sql: |
  SELECT * FROM your_table LIMIT 10

prompt: |
  请分析以下数据：
  {{data}}

output:
  format: "docx"
  filename: "分析报告_{{date}}.docx"
  save_path: "output/reports/"

notify:
  enabled: false
`

export default {
  name: 'Task',
  data() {
    return {
      tasks: [],
      showCreateDialog: false,
      newTaskYaml: DEFAULT_YAML,
    }
  },
  async mounted() {
    await this.loadTasks()
  },
  methods: {
    async loadTasks() {
      try {
        const { data } = await listTasks()
        this.tasks = data
      } catch (e) {
        console.error(e)
      }
    },
    async createTask() {
      try {
        await apiCreateTask(this.newTaskYaml)
        this.$message.success('任务创建成功')
        this.showCreateDialog = false
        await this.loadTasks()
      } catch (e) {
        this.$message.error(`创建失败: ${e.message}`)
      }
    },
    async runTask(name) {
      try {
        const { data } = await apiRunTask(name)
        this.$message.success(`执行完成: ${data.status}`)
      } catch (e) {
        this.$message.error(`执行失败: ${e.message}`)
      }
    },
    async deleteTask(name) {
      try {
        await apiDeleteTask(name)
        this.$message.success('已删除')
        await this.loadTasks()
      } catch (e) {
        this.$message.error(`删除失败: ${e.message}`)
      }
    },
  },
}
</script>
