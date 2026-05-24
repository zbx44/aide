<template>
  <div class="help-page">
    <div class="help-container">
      <h1>❓ 帮助中心</h1>
      
      <el-tabs v-model="activeTab">
        <!-- 快速入门 -->
        <el-tab-pane label="🎯 快速入门" name="quickstart">
          <div class="help-section">
            <h3>5分钟上手指南</h3>
            <el-steps direction="vertical" :active="5" finish-status="success">
              <el-step title="打开AIDE" description="双击桌面快捷方式或start.bat启动" />
              <el-step title="开始对话" description="在输入框输入你的问题，按Enter发送" />
              <el-step title="上传文件" description="点击📎按钮上传文档，AI会自动分析内容" />
              <el-step title="生成文档" description="说'帮我写一份XX报告'，AI自动生成Word/Excel/PPT" />
              <el-step title="创建定时任务" description="说'每天8点自动生成设备日报'，让AI定时工作" />
            </el-steps>
          </div>
        </el-tab-pane>

        <!-- 功能说明 -->
        <el-tab-pane label="📋 功能说明" name="features">
          <div class="help-section">
            <h3>💬 对话与问答</h3>
            <ul>
              <li>直接输入问题，AI即时回答</li>
              <li>支持上传文件（Word/Excel/PDF/图片）作为上下文</li>
              <li>支持关联知识库，AI从文档中检索答案</li>
              <li>对话历史自动保存，随时回看</li>
            </ul>
          </div>

          <div class="help-section">
            <h3>📝 文档生成</h3>
            <ul>
              <li>用自然语言描述需求，AI生成Word/Excel/PPT</li>
              <li>支持多轮修改："把第二段改成..."</li>
              <li>支持从模板生成文档</li>
              <li>可直接下载生成的文件</li>
            </ul>
          </div>

          <div class="help-section">
            <h3>📊 数据查询与分析</h3>
            <ul>
              <li>用自然语言查询数据库："查一下本月故障率"</li>
              <li>AI自动生成SQL并执行</li>
              <li>查询结果自动生成表格和解读</li>
              <li>支持创建定时任务自动出报告</li>
            </ul>
          </div>

          <div class="help-section">
            <h3>📚 知识库</h3>
            <ul>
              <li>创建知识库，上传公司制度、操作规程等文档</li>
              <li>对话时关联知识库，AI从文档中找答案</li>
              <li>支持搜索测试，验证检索效果</li>
            </ul>
          </div>

          <div class="help-section">
            <h3>🔧 技能系统</h3>
            <ul>
              <li>技能按使用频率逐步解锁，越用越强</li>
              <li>Level 1：搜索、计算、文件读取</li>
              <li>Level 2：文档生成、数据分析、通知</li>
              <li>Level 3：数据库直查、OA流程、命令执行</li>
            </ul>
          </div>

          <div class="help-section">
            <h3>🧠 自动进化</h3>
            <ul>
              <li>AI会自动记住你的偏好，越来越懂你</li>
              <li>你可以说"以后回答更简洁"来调整风格</li>
              <li>AI会定期回顾对话，自我改进</li>
            </ul>
          </div>
        </el-tab-pane>

        <!-- 使用技巧 -->
        <el-tab-pane label="💡 使用技巧" name="tips">
          <div class="help-section">
            <h3>如何描述需求更准确</h3>
            <div class="tip-pairs">
              <div class="tip-pair">
                <div class="tip-bad">❌ "写个报告"</div>
                <div class="tip-good">✅ "帮我写一份设备运行月报，本月一车间为重点，3000字左右"</div>
              </div>
              <div class="tip-pair">
                <div class="tip-bad">❌ "数据分析"</div>
                <div class="tip-good">✅ "查一下本月故障率最高的5台设备，分析原因"</div>
              </div>
              <div class="tip-pair">
                <div class="tip-bad">❌ "改一下"</div>
                <div class="tip-good">✅ "把第三段的'设备运行正常'改成'设备运行平稳，故障率下降15%'"</div>
              </div>
            </div>
          </div>

          <div class="help-section">
            <h3>常用指令</h3>
            <table class="cmd-table">
              <tr><td>以后回答更简洁</td><td>AI将采用简洁风格</td></tr>
              <tr><td>以后用表格格式回答</td><td>AI将优先使用表格</td></tr>
              <tr><td>记住：XX车间的淬火温度是860度</td><td>AI将存入长期记忆</td></tr>
              <tr><td>帮我每天8点生成设备日报</td><td>创建定时分析任务</td></tr>
            </table>
          </div>
        </el-tab-pane>

        <!-- FAQ -->
        <el-tab-pane label="❓ 常见问题" name="faq">
          <el-collapse>
            <el-collapse-item title="AI回复很慢怎么办？" name="1">
              <p>思考模型（如glm-5.1）会先推理再回答，稍微慢一些是正常的。如果超过1分钟还没响应，可能是网络问题，请联系IT支持。</p>
            </el-collapse-item>
            <el-collapse-item title="上传的文件支持哪些格式？" name="2">
              <p>支持：Word(.docx)、Excel(.xlsx)、PPT(.pptx)、PDF(.pdf)、图片(.png/.jpg/.gif/.bmp/.webp)、文本(.txt/.md/.csv/.json/.yaml)</p>
            </el-collapse-item>
            <el-collapse-item title="生成的文档在哪里下载？" name="3">
              <p>对话中AI会提供下载链接，也可以在左侧菜单「📄 文档」页面查看所有已生成的文档。</p>
            </el-collapse-item>
            <el-collapse-item title="AI记不住之前说的话？" name="4">
              <p>AI会保留最近20轮对话上下文；超过的会自动生成摘要。如果跨对话想让它记住，可以说"记住：..."，AI会存入长期记忆。</p>
            </el-collapse-item>
            <el-collapse-item title="怎么修改AI模型？" name="5">
              <p>目前模型由IT部门统一配置。如有特殊需求请联系IT支持。</p>
            </el-collapse-item>
            <el-collapse-item title="数据安全吗？" name="6">
              <p>所有数据都存储在你的本地电脑，不会上传到外部服务器。AI模型调用走公司内网，数据不出公司。</p>
            </el-collapse-item>
          </el-collapse>
        </el-tab-pane>

        <!-- 联系支持 -->
        <el-tab-pane label="📞 联系支持" name="contact">
          <div class="help-section contact-section">
            <div class="contact-item">
              <span class="contact-icon">📞</span>
              <span>内线：<strong>8001</strong></span>
            </div>
            <div class="contact-item">
              <span class="contact-icon">📧</span>
              <span>邮箱：<strong>admin@example.com</strong></span>
            </div>
            <div class="contact-item">
              <span class="contact-icon">💬</span>
              <span>钉钉群：<strong>AIDE技术支持群</strong></span>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Help',
  data() {
    return {
      activeTab: 'quickstart'
    }
  }
}
</script>

<style scoped>
.help-page {
  padding: 20px;
  overflow-y: auto;
  height: 100vh;
  background: #f5f5f5;
}
.help-container {
  max-width: 800px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  padding: 24px 32px;
  min-height: calc(100vh - 40px);
}
.help-container h1 {
  margin: 0 0 20px;
  font-size: 22px;
}
.help-section {
  margin-bottom: 24px;
}
.help-section h3 {
  font-size: 16px;
  color: #333;
  margin: 0 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #409eff;
  display: inline-block;
}
.help-section ul {
  padding-left: 20px;
  line-height: 2;
  color: #555;
}
.tip-pairs {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tip-pair {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.tip-bad {
  padding: 8px 12px;
  background: #fef0f0;
  border-radius: 6px;
  font-size: 13px;
  color: #f56c6c;
}
.tip-good {
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 6px;
  font-size: 13px;
  color: #67c23a;
}
.cmd-table {
  width: 100%;
  border-collapse: collapse;
}
.cmd-table td {
  padding: 8px 12px;
  border: 1px solid #eee;
  font-size: 13px;
}
.cmd-table td:first-child {
  font-weight: 600;
  color: #409eff;
  width: 40%;
}
.contact-section {
  padding: 20px 0;
}
.contact-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  font-size: 15px;
  border-bottom: 1px solid #f0f0f0;
}
.contact-icon { font-size: 24px; }
</style>
