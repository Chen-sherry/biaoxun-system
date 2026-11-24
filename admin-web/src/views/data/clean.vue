<template>
  <div class="data-clean-page">
    <el-row :gutter="16">
      <!-- 左侧：清洗结果卡片 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span class="title">数据清洗</span>
              <el-button type="primary" :loading="running" @click="runClean">
                {{ running ? '清洗中...' : '立即清洗' }}
              </el-button>
            </div>
          </template>

          <el-alert v-if="running" type="info" :closable="false" show-icon>
            <template #title>正在清洗全部标讯数据（8000+ 行，预计 5-10 秒）...</template>
            <el-progress :percentage="80" :indeterminate="true" style="margin-top:8px" />
          </el-alert>

          <el-empty v-if="!running && !last" description="还没清洗过。点「立即清洗」开始" />

          <div v-else-if="last" class="stats-grid">
            <div class="stat-card">
              <div class="stat-num">{{ last.stats?.rows_processed ?? '-' }}</div>
              <div class="stat-label">处理行数</div>
            </div>
            <div class="stat-card good">
              <div class="stat-num">{{ last.stats?.content_text_filled ?? '-' }}</div>
              <div class="stat-label">正文纯文本填充</div>
            </div>
            <div class="stat-card good">
              <div class="stat-num">{{ last.stats?.industry_filled ?? '-' }}</div>
              <div class="stat-label">行业分类补全</div>
            </div>
            <div class="stat-card good">
              <div class="stat-num">{{ last.stats?.notice_type_filled ?? '-' }}</div>
              <div class="stat-label">公告类型推断</div>
            </div>
            <div class="stat-card">
              <div class="stat-num">{{ last.stats?.procure_type_filled ?? '-' }}</div>
              <div class="stat-label">招采类型推断</div>
            </div>
            <div class="stat-card">
              <div class="stat-num">{{ last.stats?.customer_group_filled ?? '-' }}</div>
              <div class="stat-label">客群推断</div>
            </div>
          </div>
          <div v-if="last?.at" class="last-at">上次执行：{{ last.at }}</div>
        </el-card>
      </el-col>

      <!-- 右侧：清洗步骤说明 -->
      <el-col :span="10">
        <el-card>
          <template #header><span class="title">清洗 Pipeline</span></template>
          <el-steps direction="vertical" :active="6" finish-status="success">
            <el-step title="HTML → content_text" description="爬虫抓到的正文 HTML 自动去标签" />
            <el-step title="日期清洗" description="1900-01-01 / 空串 → NULL" />
            <el-step title="公告类型推断" description="标题关键词 → dict_notice_type" />
            <el-step title="招采类型推断" description="procure_type 关键词匹配" />
            <el-step title="客群推断" description="tenderee 关键词 → 政务/国企/民企" />
            <el-step title="行业推断" description="20 行业 + keywords → industry_id" />
          </el-steps>
        </el-card>

        <el-card style="margin-top:16px">
          <template #header><span class="title">爬虫入库自动清洗</span></template>
          <el-alert type="success" :closable="false" show-icon>
            现在 crawl.py 爬虫入库已自动走这套 pipeline，**后续爬的数据直接就是干净的**。
          </el-alert>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { runDataClean, fetchDataCleanStatus } from '@/api'

const running = ref(false)
const last = ref<any>(null)

async function loadStatus() {
  try {
    const d = await fetchDataCleanStatus()
    last.value = d
  } catch {}
}

async function runClean() {
  running.value = true
  try {
    const d = await runDataClean()
    last.value = { at: new Date().toISOString(), stats: d }
    ElMessage.success(`清洗完成！处理 ${d.rows_processed} 行`)
  } catch (e: any) {
    ElMessage.error(e?.message || '清洗失败')
  } finally {
    running.value = false
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
.stat-card { background: #f5f7fa; border-radius: 8px; padding: 16px; text-align: center; }
.stat-card.good { background: #f0f9eb; }
.stat-num { font-size: 28px; font-weight: 700; color: #303133; }
.stat-card.good .stat-num { color: #67c23a; }
.stat-label { font-size: 12px; color: #909399; margin-top: 4px; }
.last-at { margin-top: 14px; font-size: 12px; color: #909399; text-align: right; }
</style>
