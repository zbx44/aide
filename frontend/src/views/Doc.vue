<template>
  <div class="doc-page" style="padding: 20px;">
    <el-row :gutter="20">
      <!-- 左侧：创建/编辑 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>📄 生成文档</span>
          </template>
          <el-form label-position="top">
            <el-form-item label="文档类型">
              <el-radio-group v-model="docType">
                <el-radio-button value="docx">Word</el-radio-button>
                <el-radio-button value="xlsx">Excel</el-radio-button>
                <el-radio-button value="pptx">PPT</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="描述文档内容">
              <el-input
                v-model="description"
                type="textarea"
                :rows="6"
                placeholder="例如：帮我生成一份设备运行月报，包含设备名称、运行时长、故障统计，加一个故障趋势折线图..."
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="createDoc" :loading="creating">
                生成文档
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 修改区域 -->
          <el-divider v-if="currentDocId" />
          <div v-if="currentDocId">
            <h4>修改文档</h4>
            <p style="font-size: 12px; color: #999;">
              当前文档: {{ currentDocId }}
            </p>
            <el-input
              v-model="modifyInstruction"
              placeholder="输入修改指令..."
              style="margin-top: 10px;"
            >
              <template #append>
                <el-button @click="modifyDoc" :loading="modifying">修改</el-button>
              </template>
            </el-input>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：文档列表 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>📂 文档列表</span>
          </template>
          <el-table :data="docs" stripe>
            <el-table-column prop="title" label="标题" />
            <el-table-column prop="type" label="类型" width="80" />
            <el-table-column prop="updated_at" label="更新时间" width="180" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button size="small" type="primary" link
                  @click="downloadDoc(row.doc_id)">
                  下载
                </el-button>
                <el-button size="small" type="danger" link
                  @click="deleteDoc(row.doc_id)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { createDoc as apiCreateDoc, modifyDoc as apiModifyDoc,
         listDocs, downloadDoc as apiDownloadUrl, deleteDoc as apiDeleteDoc } from '../api'

export default {
  name: 'Doc',
  data() {
    return {
      docType: 'docx',
      description: '',
      modifyInstruction: '',
      currentDocId: null,
      creating: false,
      modifying: false,
      docs: [],
    }
  },
  async mounted() {
    await this.loadDocs()
  },
  methods: {
    async loadDocs() {
      try {
        const { data } = await listDocs()
        this.docs = data
      } catch (e) {
        console.error(e)
      }
    },
    async createDoc() {
      if (!this.description.trim()) return
      this.creating = true
      try {
        const { data } = await apiCreateDoc(this.description, this.docType)
        this.currentDocId = data.doc_id
        this.$message.success(`文档生成成功: ${data.title}`)
        await this.loadDocs()
      } catch (e) {
        this.$message.error(`生成失败: ${e.message}`)
      } finally {
        this.creating = false
      }
    },
    async modifyDoc() {
      if (!this.modifyInstruction.trim() || !this.currentDocId) return
      this.modifying = true
      try {
        const { data } = await apiModifyDoc(this.currentDocId, this.modifyInstruction)
        this.$message.success('文档修改成功')
        this.modifyInstruction = ''
        await this.loadDocs()
      } catch (e) {
        this.$message.error(`修改失败: ${e.message}`)
      } finally {
        this.modifying = false
      }
    },
    downloadDoc(docId) {
      window.open(apiDownloadUrl(docId), '_blank')
    },
    async deleteDoc(docId) {
      try {
        await apiDeleteDoc(docId)
        this.$message.success('已删除')
        await this.loadDocs()
      } catch (e) {
        this.$message.error(`删除失败: ${e.message}`)
      }
    },
  },
}
</script>
