<template>
  <div class="tool-page" style="padding: 20px;">
    <el-row :gutter="20">
      <!-- OCR -->
      <el-col :span="12">
        <el-card>
          <template #header><span>🔍 OCR 图文识别</span></template>
          <el-upload
            drag
            :auto-upload="false"
            :on-change="onOCRFileChange"
            accept="image/*"
          >
            <el-icon style="font-size: 48px; color: #c0c4cc;"><UploadFilled /></el-icon>
            <div>拖拽图片到此处，或点击上传</div>
          </el-upload>
          <el-button type="primary" @click="doOCR" :loading="ocrLoading"
                     style="margin-top: 16px;" :disabled="!ocrFile">
            开始识别
          </el-button>
          <div v-if="ocrResult" style="margin-top: 16px;">
            <el-input type="textarea" :rows="8" :model-value="ocrResult" readonly />
          </div>
        </el-card>
      </el-col>

      <!-- 工具列表 -->
      <el-col :span="12">
        <el-card>
          <template #header><span>🔧 可用工具</span></template>
          <el-table :data="tools" stripe>
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="description" label="说明" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script>
import { listTools, ocrRecognize } from '../api'
import { UploadFilled } from '@element-plus/icons-vue'

export default {
  name: 'Tool',
  components: { UploadFilled },
  data() {
    return {
      tools: [],
      ocrFile: null,
      ocrResult: '',
      ocrLoading: false,
    }
  },
  async mounted() {
    await this.loadTools()
  },
  methods: {
    async loadTools() {
      try {
        const { data } = await listTools()
        this.tools = data
      } catch (e) {
        console.error(e)
      }
    },
    onOCRFileChange(file) {
      this.ocrFile = file.raw
    },
    async doOCR() {
      if (!this.ocrFile) return
      this.ocrLoading = true
      this.ocrResult = ''
      try {
        const { data } = await ocrRecognize(this.ocrFile)
        this.ocrResult = data.text
      } catch (e) {
        this.ocrResult = `识别失败: ${e.message}`
      } finally {
        this.ocrLoading = false
      }
    },
  },
}
</script>
