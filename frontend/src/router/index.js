import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/chat' },
  { path: '/chat', name: 'Chat', component: () => import('../views/Chat.vue') },
  { path: '/knowledge', name: 'Knowledge', component: () => import('../views/Knowledge.vue') },
  { path: '/skills', name: 'Skills', component: () => import('../views/Skills.vue') },
  { path: '/doc', name: 'Doc', component: () => import('../views/Doc.vue') },
  { path: '/templates', name: 'Templates', component: () => import('../views/Templates.vue') },
  { path: '/agents', name: 'Agents', component: () => import('../views/Agents.vue') },
  { path: '/settings', name: 'Settings', component: () => import('../views/Settings.vue') },
  { path: '/task', name: 'Task', component: () => import('../views/Task.vue') },
  { path: '/query', name: 'Query', component: () => import('../views/Query.vue') },
  { path: '/tool', name: 'Tool', component: () => import('../views/Tool.vue') },
  { path: '/help', name: 'Help', component: () => import('../views/Help.vue') },
]

const router = createRouter({ history: createWebHistory(), routes })
export default router
