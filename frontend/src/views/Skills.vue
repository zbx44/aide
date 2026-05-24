<template>
  <div class="skill-page">
    <h2>🔧 技能管理</h2>

    <!-- 等级信息 -->
    <el-card class="level-card">
      <div class="level-header">
        <el-tag :type="levelTagType" size="large">当前等级: Level {{ levelInfo.current_level || 1 }}</el-tag>
        <span class="level-hint">{{ levelInfo.next_level_requirement }}</span>
      </div>
      <el-progress
        :percentage="levelProgress"
        :color="levelColor"
        :format="() => levelInfo.current_level === 3 ? 'MAX' : `Level ${levelInfo.current_level}`"
      />
    </el-card>

    <!-- 技能列表 -->
    <div class="skills-section">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="可见技能" name="visible">
          <div class="skills-grid">
            <div v-for="skill in visibleSkills" :key="skill.name" class="skill-card"
                 :class="'level-' + skill.level">
              <div class="skill-header">
                <span class="skill-icon">{{ levelIcon(skill.level) }}</span>
                <span class="skill-name">{{ skill.display_name }}</span>
                <el-tag size="small" :type="skillLevelTag(skill.level)">L{{ skill.level }}</el-tag>
              </div>
              <p class="skill-desc">{{ skill.description }}</p>
              <div class="skill-meta">
                <el-tag size="small" type="info">{{ skill.category }}</el-tag>
                <span class="skill-usage">已使用 {{ skill.usage_count }} 次</span>
              </div>
              <div class="skill-params" v-if="skill.parameters && skill.parameters.properties">
                <span class="params-label">参数:</span>
                <el-tag v-for="(_, key) in skill.parameters.properties" :key="key" size="small" style="margin: 2px;">
                  {{ key }}
                </el-tag>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="全部技能" name="all">
          <div class="skills-grid">
            <div v-for="skill in allSkills" :key="skill.name" class="skill-card"
                 :class="'level-' + skill.level"
                 :style="!skill.is_visible ? 'opacity: 0.5;' : ''">
              <div class="skill-header">
                <span class="skill-icon">{{ levelIcon(skill.level) }}</span>
                <span class="skill-name">{{ skill.display_name }}</span>
                <div>
                  <el-tag size="small" :type="skillLevelTag(skill.level)">L{{ skill.level }}</el-tag>
                  <el-tag v-if="skill.is_builtin" size="small" type="info">内置</el-tag>
                  <el-tag v-else size="small" type="success">自定义</el-tag>
                </div>
              </div>
              <p class="skill-desc">{{ skill.description }}</p>
              <div class="skill-meta">
                <el-tag size="small" type="info">{{ skill.category }}</el-tag>
                <span class="skill-usage">已使用 {{ skill.usage_count }} 次</span>
              </div>
              <div class="skill-actions" v-if="!skill.is_builtin">
                <el-button type="danger" size="small" @click="handleDeleteSkill(skill.name)">
                  删除
                </el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="创建技能" name="create">
          <el-form :model="newSkill" label-width="80px" style="max-width: 500px;">
            <el-form-item label="标识名">
              <el-input v-model="newSkill.name" placeholder="如: weather_query" />
            </el-form-item>
            <el-form-item label="显示名">
              <el-input v-model="newSkill.display_name" placeholder="如: 天气查询" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="newSkill.description" type="textarea" :rows="2" placeholder="功能描述" />
            </el-form-item>
            <el-form-item label="等级">
              <el-radio-group v-model="newSkill.level">
                <el-radio :value="1">Level 1 (基础)</el-radio>
                <el-radio :value="2">Level 2 (进阶)</el-radio>
                <el-radio :value="3">Level 3 (高级)</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="分类">
              <el-input v-model="newSkill.category" placeholder="如: utility" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleCreateSkill">创建技能</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script>
import { getSkills, getAllSkills, createSkill, deleteSkill } from '../api'

export default {
  name: 'Skills',
  data() {
    return {
      activeTab: 'visible',
      visibleSkills: [],
      allSkills: [],
      levelInfo: {},
      newSkill: {
        name: '',
        display_name: '',
        description: '',
        level: 1,
        category: 'custom',
        parameters: { type: 'object', properties: {} },
      },
    }
  },
  computed: {
    levelTagType() {
      const l = this.levelInfo.current_level || 1
      return l === 1 ? 'success' : l === 2 ? 'warning' : 'danger'
    },
    levelColor() {
      const l = this.levelInfo.current_level || 1
      return l === 1 ? '#67c23a' : l === 2 ? '#e6a23c' : '#f56c6c'
    },
    levelProgress() {
      const l = this.levelInfo.current_level || 1
      if (l === 3) return 100
      if (l === 1) return Math.min(100, (this.levelInfo.level1_usage || 0) / 3 * 33)
      return Math.min(100, 33 + (this.levelInfo.level2_usage || 0) / 5 * 34)
    },
  },
  async mounted() {
    await this.loadSkills()
  },
  methods: {
    levelIcon(level) {
      return level === 1 ? '🟢' : level === 2 ? '🟡' : '🔴'
    },
    skillLevelTag(level) {
      return level === 1 ? 'success' : level === 2 ? 'warning' : 'danger'
    },
    async loadSkills() {
      try {
        const [visRes, allRes] = await Promise.all([getSkills(), getAllSkills()])
        this.visibleSkills = visRes.data.skills || []
        this.levelInfo = visRes.data.level_info || {}
        this.allSkills = (allRes.data || []).map(s => ({
          ...s,
          is_visible: this.visibleSkills.some(v => v.name === s.name)
        }))
      } catch (e) { console.error(e) }
    },
    async handleCreateSkill() {
      try {
        await createSkill(this.newSkill)
        this.$message.success('技能创建成功！')
        this.newSkill = { name: '', display_name: '', description: '', level: 1, category: 'custom', parameters: { type: 'object', properties: {} } }
        await this.loadSkills()
      } catch (e) {
        this.$message.error('创建失败: ' + e.message)
      }
    },
    async handleDeleteSkill(name) {
      try {
        await this.$confirm('确定删除此技能？', '提示', { type: 'warning' })
        await deleteSkill(name)
        this.$message.success('已删除')
        await this.loadSkills()
      } catch (e) {
        if (e !== 'cancel') this.$message.error('删除失败: ' + e.message)
      }
    },
  },
  watch: {
    activeTab(v) {
      if (v === 'all' || v === 'visible') this.loadSkills()
    }
  },
}
</script>

<style scoped>
.skill-page {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}
.level-card {
  margin-bottom: 20px;
}
.level-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.level-hint { font-size: 13px; color: #999; }
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}
.skill-card {
  padding: 16px;
  border-radius: 10px;
  border: 1px solid #e4e7ed;
  background: #fff;
  transition: box-shadow 0.2s;
}
.skill-card:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.skill-card.level-1 { border-left: 4px solid #67c23a; }
.skill-card.level-2 { border-left: 4px solid #e6a23c; }
.skill-card.level-3 { border-left: 4px solid #f56c6c; }
.skill-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.skill-name { font-weight: 600; flex: 1; }
.skill-desc { font-size: 13px; color: #666; margin: 6px 0; line-height: 1.5; }
.skill-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.skill-usage { font-size: 12px; color: #999; }
.skill-params { margin-top: 8px; font-size: 12px; }
.params-label { color: #999; margin-right: 4px; }
.skill-actions { margin-top: 8px; text-align: right; }
</style>
