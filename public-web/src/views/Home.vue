<template>
  <div class="home-page">
    <!-- Hero 区：大搜索框 + 高级筛选 -->
    <section class="hero">
      <div class="hero-inner">
        <h1 class="hero-title">🏛️ 全国标讯 · 智能搜索</h1>
        <p class="hero-sub">聚合公共资源交易平台、政府采购网、招投标公告，AI 语义匹配 + 多条件精准筛选</p>

        <!-- AI 搜索框常驻 -->
        <div class="ai-search-box">
          <el-input
            v-model="aiKeyword"
            size="large"
            placeholder="试试：帮我找培训场地相关的招标公告"
            @keyup.enter="onAiSearch"
            clearable
          >
            <template #prefix><el-icon><MagicStick /></el-icon></template>
            <template #append>
              <el-button :icon="MagicStick" type="primary" @click="onAiSearch">AI 智能匹配</el-button>
            </template>
          </el-input>
          <div class="search-switch">
            <el-radio-group v-model="searchMode" size="small">
              <el-radio-button value="ai">🤖 AI 智能（自然语言）</el-radio-button>
              <el-radio-button value="kw">🔍 传统关键词</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <!-- 折叠式高级筛选面板 -->
        <el-collapse v-model="filterOpen" class="filter-panel" :expand-icon-position="'start'">
          <el-collapse-item name="open">
            <template #title>
              <span class="filter-title">🎛️ 高级筛选（点击展开 / 收起）</span>
            </template>
            <el-row :gutter="16">
              <el-col :span="6">
                <el-form-item label="公告类型">
                  <el-select v-model="filter.notice_type_id" clearable placeholder="全部" style="width:100%">
                    <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="招采类型">
                  <el-input v-model="filter.procure_type" placeholder="如 公开招标" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="地区代码">
                  <el-input v-model="filter.region_code" placeholder="如 110000" clearable />
                </el-form-item>
              </el-col>
              <el-col :span="6">
                <el-form-item label="客群">
                  <el-select v-model="filter.customer_group" clearable placeholder="全部" style="width:100%">
                    <el-option label="政务" value="政务" />
                    <el-option label="国企" value="国企" />
                    <el-option label="民企" value="民企" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="发布时间范围">
                  <el-date-picker v-model="filter.date_range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="中标时间范围">
                  <el-date-picker v-model="filter.winner_date_range" type="daterange" start-placeholder="开始" end-placeholder="结束" value-format="YYYY-MM-DD" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <div style="text-align:right">
              <el-button @click="resetFilter">重置</el-button>
              <el-button type="primary" @click="onTraditionalSearch">应用筛选 →</el-button>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </section>

    <!-- 门户统计 -->
    <section class="stats-bar">
      <div class="stat-item">
        <div class="stat-num">{{ stats.total_bids }}</div>
        <div class="stat-label">累计标讯</div>
      </div>
      <div class="stat-item">
        <div class="stat-num">{{ stats.today_new }}</div>
        <div class="stat-label">今日新增</div>
      </div>
      <div class="stat-item">
        <div class="stat-num">{{ stats.sources_enabled }}</div>
        <div class="stat-label">启用采集源</div>
      </div>
      <div class="stat-item">
        <div class="stat-num">实时</div>
        <div class="stat-label">自动更新中</div>
      </div>
    </section>

    <!-- 热门标讯列表 -->
    <section class="content-section">
      <div class="section-header">
        <h2>🔥 最新标讯</h2>
        <el-button link type="primary" @click="$router.push('/search')">查看全部 →</el-button>
      </div>
      <el-row :gutter="16">
        <el-col v-for="b in hotBids" :key="b.id" :span="12" style="margin-bottom:12px">
          <div class="bid-card" @click="$router.push(`/bid/${b.id}`)">
            <div class="bid-title">{{ b.title }}</div>
            <div class="bid-meta">
              <el-tag v-if="b.procure_type" size="small" type="primary">{{ b.procure_type }}</el-tag>
              <span>{{ formatTime(b.publish_time) }}</span>
              <span v-if="b.region_name">· {{ b.region_name }}</span>
            </div>
            <div class="bid-sub" v-if="b.tenderee">采购人：{{ b.tenderee }}</div>
          </div>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MagicStick } from '@element-plus/icons-vue'
import { fetchPublicHot, fetchPortalStats, fetchPublicNoticeTypes } from '@/api'

const router = useRouter()
const aiKeyword = ref('')
const searchMode = ref<'ai' | 'kw'>('ai')
const filterOpen = ref<string[]>([])  // 默认收起，点击展开
const noticeTypes = ref<any[]>([])
const hotBids = ref<any[]>([])
const stats = reactive({ total_bids: 0, today_new: 0, sources_enabled: 0 })
const filter = reactive({
  notice_type_id: null as number | null,
  procure_type: '',
  region_code: '',
  customer_group: '',
  date_range: null as any,
  winner_date_range: null as any,
})

function onAiSearch() {
  if (!aiKeyword.value.trim()) { router.push('/ai-match'); return }
  // 整句传给 AI 检索页，由后端转译（不再本地拆词）
  router.push({ path: '/ai-match', query: { q: aiKeyword.value.trim() } })
}
function onTraditionalSearch() {
  const q: any = {}
  if (aiKeyword.value.trim()) q.kw = aiKeyword.value.trim()
  if (filter.notice_type_id) q.notice_type_id = filter.notice_type_id
  if (filter.procure_type) q.procure_type = filter.procure_type
  if (filter.region_code) q.region_code = filter.region_code
  if (filter.customer_group) q.customer_group = filter.customer_group
  if (filter.date_range) { q.date_from = filter.date_range[0]; q.date_to = filter.date_range[1] }
  if (filter.winner_date_range) { q.winner_date_from = filter.winner_date_range[0]; q.winner_date_to = filter.winner_date_range[1] }
  router.push({ name: 'search', query: q })
}
function resetFilter() {
  filter.notice_type_id = null; filter.procure_type = ''; filter.region_code = ''
  filter.customer_group = ''; filter.date_range = null; filter.winner_date_range = null
}
function formatTime(t: any) {
  if (!t) return ''
  return String(t).replace('T', ' ').slice(0, 10)
}

onMounted(async () => {
  try {
    const [hot, s, nts] = await Promise.all([
      fetchPublicHot(16), fetchPortalStats(), fetchPublicNoticeTypes(),
    ])
    hotBids.value = hot
    Object.assign(stats, s)
    noticeTypes.value = nts || []
  } catch (e) { console.error(e) }
})
</script>

<style scoped>
.hero {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 48px 24px 32px;
  color: #fff;
}
.hero-inner { max-width: 900px; margin: 0 auto; }
.hero-title { text-align: center; font-size: 32px; margin: 0 0 8px; }
.hero-sub { text-align: center; opacity: 0.9; margin-bottom: 32px; font-size: 15px; }

.ai-search-box { max-width: 700px; margin: 0 auto; }
.ai-search-box :deep(.el-input__wrapper) { font-size: 16px; height: 48px; }
.search-switch { text-align: center; margin-top: 16px; }

.filter-panel { max-width: 900px; margin: 24px auto 0; background: rgba(255,255,255,0.95); border-radius: 8px; padding: 4px 16px; }
.filter-title { font-size: 14px; font-weight: 600; color: #667eea; }

.stats-bar {
  max-width: 1200px; margin: -16px auto 24px; padding: 20px;
  background: #fff; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06);
  display: grid; grid-template-columns: repeat(4,1fr);
}
.stat-item { text-align: center; }
.stat-num { font-size: 28px; font-weight: 700; color: #1e5799; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }

.content-section { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.section-header h2 { margin: 0; font-size: 20px; }

.bid-card {
  background: #fff; border-radius: 8px; padding: 16px; cursor: pointer;
  transition: all .2s; box-shadow: 0 2px 8px rgba(0,0,0,0.05); height: 100%;
}
.bid-card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,0.1); }
.bid-title { font-size: 15px; font-weight: 600; color: #303133; line-height: 1.5; margin-bottom: 8px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.bid-meta { font-size: 12px; color: #909399; display: flex; gap: 8px; align-items: center; margin-bottom: 4px; flex-wrap: wrap; }
.bid-sub { font-size: 12px; color: #606266; }
</style>
