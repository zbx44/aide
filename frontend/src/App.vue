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
          <el-icon><ChatDotRound /></el-icon><span>对话</span>
        </el-menu-item>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon><span>知识库</span>
        </el-menu-item>
        <el-menu-item index="/doc">
          <el-icon><Document /></el-icon><span>文档</span>
        </el-menu-item>
        <el-menu-item index="/templates">
          <el-icon><Notebook /></el-icon><span>模板</span>
        </el-menu-item>
        <el-menu-item index="/agents">
          <el-icon><Monitor /></el-icon><span>智能体</span>
        </el-menu-item>
        <el-menu-item index="/task">
          <el-icon><DataAnalysis /></el-icon><span>任务</span>
        </el-menu-item>
        <el-menu-item index="/query">
          <el-icon><Search /></el-icon><span>查数据</span>
        </el-menu-item>
        <el-menu-item index="/skills">
          <el-icon><SetUp /></el-icon><span>技能</span>
        </el-menu-item>
        <el-menu-item index="/tool">
          <el-icon><SetUp /></el-icon><span>工具</span>
        </el-menu-item>
        <el-menu-item index="/help">
          <el-icon><QuestionFilled /></el-icon><span>帮助</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon><span>设置</span>
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
