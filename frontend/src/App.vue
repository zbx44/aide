<template>
  <el-container style="height: 100vh;">
    <!-- 侧边栏 -->
    <el-aside width="200px" style="background: #304156;">
      <div style="padding: 20px; text-align: center; color: #fff;">
        <h3>🧭 知行</h3>
        <p style="font-size: 12px; opacity: 0.7;">AI Assistant</p>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/chat">
          <span>💬 对话</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <span>📚 知识库</span>
        </el-menu-item>
        <el-menu-item index="/doc">
          <span>📄 文档</span>
        </el-menu-item>
        <el-menu-item index="/templates">
          <span>📝 模板</span>
        </el-menu-item>
        <el-menu-item index="/agents">
          <span>🤖 智能体</span>
        </el-menu-item>
        <el-menu-item index="/task">
          <span>📊 任务</span>
        </el-menu-item>
        <el-menu-item index="/query">
          <span>🔍 查数据</span>
        </el-menu-item>
        <el-menu-item index="/skills">
          <span>🔧 技能</span>
        </el-menu-item>
        <el-menu-item index="/tool">
          <span>🛠 工具</span>
        </el-menu-item>
        <el-menu-item index="/help">
          <span>❓ 帮助</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <span>⚙️ 设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容 -->
    <el-main style="padding: 0;">
      <router-view />
    </el-main>
  </el-container>
</template>

<script>
export default {
  name: 'App',
}
</script>

<style>
body {
  margin: 0;
  font-family: 'Microsoft YaHei', sans-serif;
}
</style>
