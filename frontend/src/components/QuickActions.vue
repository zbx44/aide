<template>
  <div class="quick-actions">
    <el-button 
      v-for="action in actions" 
      :key="action.id"
      size="small" 
      round
      @click="handleAction(action)"
    >
      {{ action.icon }} {{ action.label }}
    </el-button>
  </div>
</template>

<script>
/**
 * 功能快捷按钮组件
 * 放在对话页面顶部，让用户不用打字也能快速使用功能
 */
export default {
  name: 'QuickActions',
  data() {
    return {
      actions: [
        { id: 'write-doc', icon: '📝', label: '写文档', route: '/doc', prompt: '帮我写一份' },
        { id: 'query-data', icon: '📊', label: '查数据', route: '/chat', prompt: '查一下' },
        { id: 'ask-knowledge', icon: '🔍', label: '问知识', route: '/chat', prompt: '请问' },
        { id: 'scheduled-task', icon: '📋', label: '定时任务', route: '/task', prompt: null },
      ]
    }
  },
  methods: {
    handleAction(action) {
      if (action.route === '/chat' && action.prompt) {
        // 如果是聊天类快捷操作，设置输入框预填充文本
        this.$emit('prefill', action.prompt)
      } else {
        // 否则路由跳转
        this.$router.push(action.route)
      }
    }
  }
}
</script>

<style scoped>
.quick-actions {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: #fafafa;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}
.quick-actions .el-button {
  font-size: 13px;
  border-color: #dcdfe6;
  color: #606266;
}
.quick-actions .el-button:hover {
  color: #409eff;
  border-color: #c6e2ff;
  background: #ecf5ff;
}
</style>
