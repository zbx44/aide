<template>
  <transition name="tip-slide">
    <div v-if="visible" class="feature-tip" :class="position">
      <div class="tip-content">
        <span class="tip-icon">💡</span>
        <span class="tip-text">{{ tip.text }}</span>
      </div>
      <button class="tip-close" @click="dismiss">✕</button>
    </div>
  </transition>
</template>

<script>
/**
 * 渐进式功能提示组件
 * 
 * 使用方式：
 * <FeatureTip tip-id="first-upload" text="你可以上传文件让我分析，试试📎" />
 * 
 * 每个 tip-id 只显示一次，dismiss 后记录到 localStorage
 */

const DISMISSED_KEY = 'aide_dismissed_tips'
const SHOWN_KEY = 'aide_shown_tips'

export default {
  name: 'FeatureTip',
  props: {
    tipId: { type: String, required: true },
    text: { type: String, default: '' },
    position: { type: String, default: 'bottom-right' }, // bottom-right, bottom-left, top-right
  },
  data() {
    return {
      visible: false,
      tip: { text: '' },
    }
  },
  mounted() {
    // 检查是否已看过
    const dismissed = JSON.parse(localStorage.getItem(DISMISSED_KEY) || '[]')
    if (dismissed.includes(this.tipId)) {
      return
    }
    
    this.tip = { text: this.text }
    // 延迟显示，让用户先看到主体内容
    setTimeout(() => {
      this.visible = true
      // 记录已显示过（但不算 dismissed）
      const shown = JSON.parse(localStorage.getItem(SHOWN_KEY) || '[]')
      if (!shown.includes(this.tipId)) {
        shown.push(this.tipId)
        localStorage.setItem(SHOWN_KEY, JSON.stringify(shown))
      }
    }, 2000)
  },
  methods: {
    dismiss() {
      this.visible = false
      const dismissed = JSON.parse(localStorage.getItem(DISMISSED_KEY) || '[]')
      if (!dismissed.includes(this.tipId)) {
        dismissed.push(this.tipId)
        localStorage.setItem(DISMISSED_KEY, JSON.stringify(dismissed))
      }
    }
  }
}
</script>

<style scoped>
.feature-tip {
  position: fixed;
  z-index: 8000;
  background: #fff;
  border-radius: 10px;
  padding: 12px 16px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  border: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 360px;
}
.feature-tip.bottom-right { bottom: 80px; right: 24px; }
.feature-tip.bottom-left { bottom: 80px; left: 24px; }
.feature-tip.top-right { top: 80px; right: 24px; }
.tip-content {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
}
.tip-icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.tip-text { font-size: 13px; color: #333; line-height: 1.5; }
.tip-close {
  background: none;
  border: none;
  cursor: pointer;
  color: #999;
  font-size: 14px;
  padding: 2px 4px;
  flex-shrink: 0;
}
.tip-close:hover { color: #333; }

.tip-slide-enter-active { transition: all 0.3s ease; }
.tip-slide-leave-active { transition: all 0.2s ease; }
.tip-slide-enter-from { opacity: 0; transform: translateY(20px); }
.tip-slide-leave-to { opacity: 0; transform: translateY(10px); }
</style>
