import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

// 按需引入 Element Plus 图标（避免全量注册增加包体积）
import {
  ChatDotRound, Cloudy, Coin, Collection, Connection, Cpu,
  DataAnalysis, Delete, Document, FolderOpened, MagicStick,
  Message, Monitor, Notebook, Paperclip, Promotion,
  QuestionFilled, Search, SetUp, Setting
} from '@element-plus/icons-vue'

const iconMap = {
  ChatDotRound, Cloudy, Coin, Collection, Connection, Cpu,
  DataAnalysis, Delete, Document, FolderOpened, MagicStick,
  Message, Monitor, Notebook, Paperclip, Promotion,
  QuestionFilled, Search, SetUp, Setting
}

const app = createApp(App)
app.use(ElementPlus)
for (const [key, component] of Object.entries(iconMap)) {
  app.component(key, component)
}
app.use(router)
app.mount('#app')
