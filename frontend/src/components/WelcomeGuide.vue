<template>
  <div class="welcome-guide" v-if="visible">
    <div class="welcome-overlay">
      <div class="welcome-card">
        <button class="close-btn" @click="close" title="关闭">✕</button>
        
        <div class="welcome-header">
          <div class="welcome-icon">🧭</div>
          <h2>你好！我是知行，你的AI助手</h2>
          <p class="welcome-subtitle">我能帮你做这些事：</p>
        </div>

        <div class="feature-grid">
          <div class="feature-item" @click="tryExample('帮我写一份设备运行月报')">
            <div class="feature-icon">📝</div>
            <div class="feature-name">写文档</div>
            <div class="feature-desc">日报周报、分析报告</div>
          </div>
          <div class="feature-item" @click="tryExample('查一下本月故障率最高的设备')">
            <div class="feature-icon">📊</div>
            <div class="feature-name">查数据</div>
            <div class="feature-desc">设备运行、故障统计</div>
          </div>
          <div class="feature-item" @click="tryExample('总结一下这份文件的关键要点')">
            <div class="feature-icon">📄</div>
            <div class="feature-name">分析报告</div>
            <div class="feature-desc">故障分析、数据解读</div>
          </div>
          <div class="feature-item" @click="tryExample('我们的设备采购流程是什么')">
            <div class="feature-icon">🔍</div>
            <div class="feature-name">问知识</div>
            <div class="feature-desc">公司制度、操作规程</div>
          </div>
        </div>

        <div class="examples-section">
          <p class="examples-title">试试这样问我 👇</p>
          <div class="example-list">
            <div 
              v-for="(ex, idx) in examples" 
              :key="idx" 
              class="example-item"
              @click="tryExample(ex.text)"
            >
              <span class="example-icon">💬</span>
              <span class="example-text">{{ ex.text }}</span>
              <span class="example-action">试试</span>
            </div>
          </div>
        </div>

        <div class="welcome-footer">
          <el-checkbox v-model="dontShowAgain">下次不再显示此引导</el-checkbox>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
const STORAGE_KEY = 'aide_welcome_dismissed'

export default {
  name: 'WelcomeGuide',
  data() {
    return {
      visible: false,
      dontShowAgain: false,
      examples: [
        { text: '帮我写一份设备运行月报' },
        { text: '查一下本月故障率最高的5台设备' },
        { text: '总结一下这份文件的关键要点' },
        { text: '把这段数据整理成表格' },
      ]
    }
  },
  mounted() {
    const dismissed = localStorage.getItem(STORAGE_KEY)
    if (!dismissed) {
      this.visible = true
    }
  },
  methods: {
    close() {
      if (this.dontShowAgain) {
        localStorage.setItem(STORAGE_KEY, 'true')
      }
      this.visible = false
    },
    tryExample(text) {
      this.close()
      this.$emit('try-example', text)
    },
    show() {
      this.visible = true
    }
  }
}
</script>

<style scoped>
.welcome-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.welcome-card {
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  max-width: 600px;
  width: 90%;
  position: relative;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}
.close-btn {
  position: absolute;
  top: 12px;
  right: 16px;
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #999;
  padding: 4px 8px;
}
.close-btn:hover { color: #333; }
.welcome-header {
  text-align: center;
  margin-bottom: 24px;
}
.welcome-icon {
  font-size: 48px;
  margin-bottom: 8px;
}
.welcome-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  color: #333;
}
.welcome-subtitle {
  color: #999;
  font-size: 14px;
  margin: 0;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}
.feature-item {
  text-align: center;
  padding: 16px 8px;
  border-radius: 12px;
  border: 1px solid #e4e7ed;
  cursor: pointer;
  transition: all 0.2s;
}
.feature-item:hover {
  border-color: #409eff;
  background: #ecf5ff;
  transform: translateY(-2px);
}
.feature-icon { font-size: 28px; margin-bottom: 6px; }
.feature-name { font-weight: 600; font-size: 14px; color: #333; }
.feature-desc { font-size: 12px; color: #999; margin-top: 2px; }
.examples-section {
  margin-bottom: 20px;
}
.examples-title {
  font-size: 14px;
  color: #666;
  margin: 0 0 12px;
}
.example-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.example-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 8px;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.2s;
}
.example-item:hover {
  background: #ecf5ff;
}
.example-icon { font-size: 16px; }
.example-text { flex: 1; font-size: 14px; color: #333; }
.example-action {
  font-size: 12px;
  color: #409eff;
  padding: 2px 8px;
  border: 1px solid #409eff;
  border-radius: 10px;
}
.welcome-footer {
  text-align: center;
  padding-top: 12px;
  border-top: 1px solid #eee;
}
</style>
