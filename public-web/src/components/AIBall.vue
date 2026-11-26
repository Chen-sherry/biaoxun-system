<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Close, Delete, Promotion, MagicStick } from '@element-plus/icons-vue'
import axios from 'axios'

// ============================================================
// AI 悬浮球（P2 多轮对话）
// - 右下角常驻可拖拽球体，点击展开对话面板（面板标题栏也可拖动）
// - 登录 / 会员购买页隐藏；会话 localStorage 持久化（上限 200 条）
// - 检索结果卡片 → 详情页；401/403 → 会员提示；429 → 频控提示
// ============================================================

const router = useRouter()
const route = useRoute()

const API = import.meta.env.VITE_API_BASE || ''

// ---- 可见性：登录 / 会员购买页不显示 ----
const visible = computed(() =>
  !['login', 'member'].includes(String(route.name || '')))

// ---- 状态 ----
interface BidResult {
  id: number
  title: string
  publish_time?: string
  score?: number
  reason?: string
  budget?: string
  tenderee?: string
}
interface Msg {
  role: 'user' | 'assistant'
  content: string
  results?: BidResult[]
  query?: string      // 触发本次结果的用户问题（「查看全部」跳转用）
  truncated?: boolean // 后端记忆窗口截断提示
}

const open = ref(false)
const msgs = ref<Msg[]>([])
const input = ref('')
const loading = ref(false)
const loadingText = ref('AI 思考中…')
const chatEnabled = ref(true)
const msgsBox = ref<HTMLElement | null>(null)

let loadingTimer: number | undefined

// ---- 持久化 ----
const MSG_KEY = 'biaoxun_ai_chat'
const BALL_KEY = 'biaoxun_ai_ball_pos'
const PANEL_KEY = 'biaoxun_ai_panel_pos'
const MAX_MSGS = 200

function saveMsgs() {
  if (msgs.value.length > MAX_MSGS) {
    msgs.value.splice(0, msgs.value.length - MAX_MSGS)
  }
  try {
    localStorage.setItem(MSG_KEY, JSON.stringify(msgs.value))
  } catch { /* 空间不足等忽略 */ }
}

function loadMsgs() {
  try {
    const raw = localStorage.getItem(MSG_KEY)
    if (raw) msgs.value = JSON.parse(raw) || []
  } catch { /* 损坏则从空开始 */ }
}

// ---- 球体拖拽（pointer 事件，位移 <5px 视为点击）----
const BALL = 56
const ballPos = ref({ x: 0, y: 0 })

function defaultBall() {
  return {
    x: Math.max(8, window.innerWidth - BALL - 24),
    y: Math.max(8, window.innerHeight - BALL - 24),
  }
}
function clampBall() {
  ballPos.value.x = Math.min(Math.max(8, ballPos.value.x), window.innerWidth - BALL - 8)
  ballPos.value.y = Math.min(Math.max(8, ballPos.value.y), window.innerHeight - BALL - 8)
}

function onBallDown(e: PointerEvent) {
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture(e.pointerId)
  const sx = e.clientX, sy = e.clientY
  const ox = ballPos.value.x, oy = ballPos.value.y
  let moved = false
  const move = (ev: PointerEvent) => {
    const dx = ev.clientX - sx, dy = ev.clientY - sy
    if (!moved && Math.hypot(dx, dy) > 5) moved = true
    if (moved) {
      ballPos.value.x = ox + dx
      ballPos.value.y = oy + dy
      clampBall()
    }
  }
  const up = (ev: PointerEvent) => {
    el.removeEventListener('pointermove', move)
    el.removeEventListener('pointerup', up)
    try { el.releasePointerCapture(ev.pointerId) } catch { /* 已释放 */ }
    if (moved) {
      try { localStorage.setItem(BALL_KEY, JSON.stringify(ballPos.value)) } catch { /* 忽略 */ }
    } else {
      togglePanel()
    }
  }
  el.addEventListener('pointermove', move)
  el.addEventListener('pointerup', up)
}

// ---- 面板拖拽（桌面端标题栏；移动端为底部抽屉不拖）----
const PANEL_W = 380
const PANEL_H = 560
const panelPos = ref({ x: 0, y: 0 })
const isMobile = ref(window.innerWidth <= 768)

function defaultPanel() {
  return {
    x: Math.max(8, window.innerWidth - PANEL_W - 24),
    y: Math.max(8, Math.min(window.innerHeight - 300, window.innerHeight - PANEL_H - 96)),
  }
}
function clampPanel() {
  panelPos.value.x = Math.min(Math.max(8, panelPos.value.x), window.innerWidth - PANEL_W - 8)
  panelPos.value.y = Math.min(Math.max(8, panelPos.value.y), window.innerHeight - 280)
}

function onHeaderDown(e: PointerEvent) {
  if (isMobile.value) return
  const el = e.currentTarget as HTMLElement
  el.setPointerCapture(e.pointerId)
  const sx = e.clientX, sy = e.clientY
  const ox = panelPos.value.x, oy = panelPos.value.y
  const move = (ev: PointerEvent) => {
    panelPos.value.x = ox + (ev.clientX - sx)
    panelPos.value.y = oy + (ev.clientY - sy)
    clampPanel()
  }
  const up = (ev: PointerEvent) => {
    el.removeEventListener('pointermove', move)
    el.removeEventListener('pointerup', up)
    try { el.releasePointerCapture(ev.pointerId) } catch { /* 已释放 */ }
    try { localStorage.setItem(PANEL_KEY, JSON.stringify(panelPos.value)) } catch { /* 忽略 */ }
  }
  el.addEventListener('pointermove', move)
  el.addEventListener('pointerup', up)
}

const panelStyle = computed(() =>
  isMobile.value ? {} : { left: panelPos.value.x + 'px', top: panelPos.value.y + 'px' })

// ---- Markdown 轻量渲染（加粗 / 行内代码 / 列表 / 换行）----
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
function inlineFmt(t: string): string {
  return t
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}
function renderMd(src: string): string {
  const lines = escapeHtml(src || '').split(/\r?\n/)
  const out: string[] = []
  let list: 'ul' | 'ol' | null = null
  let para: string[] = []
  const flushPara = () => {
    if (para.length) { out.push(`<p>${inlineFmt(para.join('<br>'))}</p>`); para = [] }
  }
  const closeList = () => {
    if (list) { out.push(list === 'ul' ? '</ul>' : '</ol>'); list = null }
  }
  for (const raw of lines) {
    const ul = raw.match(/^\s*[-*]\s+(.*)$/)
    const ol = raw.match(/^\s*\d+[.、)]\s+(.*)$/)
    const h = raw.match(/^#{1,4}\s+(.*)$/)
    if (ul || ol) {
      flushPara()
      const kind: 'ul' | 'ol' = ul ? 'ul' : 'ol'
      if (list !== kind) { closeList(); out.push(`<${kind}>`); list = kind }
      out.push(`<li>${inlineFmt((ul || ol)![1])}</li>`)
    } else if (h) {
      flushPara(); closeList()
      out.push(`<p class="md-h">${inlineFmt(h[1])}</p>`)
    } else if (!raw.trim()) {
      flushPara(); closeList()
    } else {
      closeList(); para.push(raw)
    }
  }
  flushPara(); closeList()
  return out.join('')
}

// ---- 滚动到底 ----
function scrollBottom() {
  nextTick(() => {
    if (msgsBox.value) msgsBox.value.scrollTop = msgsBox.value.scrollHeight
  })
}
watch(() => msgs.value.length, scrollBottom)

// ---- 会员提示（与 AIMatch 同款交互）----
async function memberGate(status: number) {
  try {
    await ElMessageBox.alert(
      'AI 助手是付费会员专属功能，开通会员后即可使用。\n（当前为演示环境，会员开通功能即将上线）',
      '会员专享',
      {
        type: 'warning',
        confirmButtonText: '查看会员套餐',
        cancelButtonText: '登录',
        showCancelButton: true,
        distinguishCancelAndClose: true,
        center: true,
      },
    )
    router.push('/member')
  } catch (action) {
    if (action === 'cancel') router.push('/login')
  }
}

// ---- 发送 ----
async function send(preset?: string) {
  const q = (preset ?? input.value).trim()
  if (!q || loading.value) return
  if (!chatEnabled.value) { ElMessage.info('AI 助手暂未开放'); return }

  input.value = ''
  msgs.value.push({ role: 'user', content: q })
  saveMsgs()
  scrollBottom()

  loading.value = true
  loadingText.value = 'AI 思考中…'
  loadingTimer = window.setTimeout(() => {
    loadingText.value = '正在查询知识库，约 10~30 秒…'
  }, 6000)

  try {
    const token = localStorage.getItem('token')
    const res = await axios.post(
      `${API}/api/v1/ai/chat`,
      {
        messages: msgs.value.map(m => ({ role: m.role, content: m.content })),
        inject_context: true,
      },
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        timeout: 120000,
      },
    )
    if (res.data.code === 0) {
      const d = res.data.data || {}
      const hasResults = Array.isArray(d.results) && d.results.length > 0
      msgs.value.push({
        role: 'assistant',
        content: d.reply || '（AI 未返回内容）',
        results: hasResults ? d.results : undefined,
        query: hasResults ? q : undefined,
        truncated: !!d.truncated,
      })
      saveMsgs()
    } else {
      msgs.value.push({
        role: 'assistant',
        content: `⚠️ ${res.data.msg || res.data.message || '对话失败'}`,
      })
      saveMsgs()
    }
  } catch (e: any) {
    const status = e?.response?.status
    if (status === 401 || status === 403) {
      // 回退掉刚才的用户消息，避免留下发不出去的气泡
      msgs.value.pop()
      saveMsgs()
      await memberGate(status)
    } else if (status === 429) {
      msgs.value.push({
        role: 'assistant',
        content: `⚠️ ${e?.response?.data?.detail || '今日对话次数已达上限，请明天再来'}`,
      })
      saveMsgs()
    } else if (status === 400) {
      msgs.value.push({ role: 'assistant', content: '⚠️ 消息不能为空' })
      saveMsgs()
    } else {
      msgs.value.push({
        role: 'assistant',
        content: '⚠️ AI 暂时不可用，请稍后再试',
      })
      saveMsgs()
    }
  } finally {
    window.clearTimeout(loadingTimer)
    loading.value = false
    scrollBottom()
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

// ---- 面板操作 ----
function togglePanel() {
  open.value = !open.value
  if (open.value) scrollBottom()
}
function closePanel() { open.value = false }
function clearMsgs() {
  msgs.value = []
  try { localStorage.removeItem(MSG_KEY) } catch { /* 忽略 */ }
  ElMessage.success('已清空会话')
}
function goBid(id: number) { router.push(`/bid/${id}`) }
function viewAll(m: Msg) {
  const kw = (m.query || '').trim()
  router.push(kw ? `/ai-match?kw=${encodeURIComponent(kw)}` : '/ai-match')
  closePanel()
}

// 示例问题（空会话时点即发）
const SUGGESTIONS = [
  '帮我找合肥最近一个月的学校招标',
  '最近新增多少条标讯',
  '招标公告和中标公告有什么区别',
]

// ---- 初始化 ----
function onResize() {
  isMobile.value = window.innerWidth <= 768
  clampBall()
  clampPanel()
}

onMounted(async () => {
  loadMsgs()
  try {
    const raw = localStorage.getItem(BALL_KEY)
    ballPos.value = raw ? JSON.parse(raw) : defaultBall()
  } catch { ballPos.value = defaultBall() }
  clampBall()
  try {
    const raw = localStorage.getItem(PANEL_KEY)
    panelPos.value = raw ? JSON.parse(raw) : defaultPanel()
  } catch { panelPos.value = defaultPanel() }
  clampPanel()
  window.addEventListener('resize', onResize)

  // 探测 AI 服务状态
  try {
    const res = await axios.get(`${API}/api/v1/ai/config`, { timeout: 10000 })
    if (res.data.code === 0) chatEnabled.value = !!res.data.data?.chat_enabled
  } catch { /* 保持可用，发送时再报错 */ }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  window.clearTimeout(loadingTimer)
})
</script>

<template>
  <div v-if="visible" class="aiball-root">
    <!-- ===== 悬浮球 ===== -->
    <div
      class="aiball"
      :class="{ open }"
      :style="{ left: ballPos.x + 'px', top: ballPos.y + 'px' }"
      :title="chatEnabled ? '标讯 AI 助手' : 'AI 助手暂未开放'"
      @pointerdown="onBallDown"
    >
      <el-icon :size="26"><ChatDotRound /></el-icon>
      <span class="aiball-ring" aria-hidden="true"></span>
    </div>

    <!-- ===== 对话面板 ===== -->
    <transition name="aipanel">
      <div
        v-if="open"
        class="aipanel"
        :class="{ mobile: isMobile }"
        :style="panelStyle"
      >
        <!-- 标题栏（桌面可拖动） -->
        <div class="aipanel-hd" @pointerdown="onHeaderDown">
          <div class="hd-left">
            <span class="hd-icon"><el-icon><MagicStick /></el-icon></span>
            <div class="hd-title">
              <b>标讯 AI 助手</b>
              <span>多轮对话 · 会员专享</span>
            </div>
          </div>
          <div class="hd-acts">
            <button class="hd-btn" title="清空会话" @click.stop="clearMsgs">
              <el-icon><Delete /></el-icon>
            </button>
            <button class="hd-btn" title="收起" @click.stop="closePanel">
              <el-icon><Close /></el-icon>
            </button>
          </div>
        </div>

        <!-- 消息区 -->
        <div ref="msgsBox" class="aipanel-body">
          <!-- 空状态 -->
          <div v-if="!msgs.length" class="ai-empty">
            <div class="ai-empty-icon"><el-icon :size="30"><ChatDotRound /></el-icon></div>
            <p class="ai-empty-title">你好，我是标讯 AI 助手</p>
            <p class="ai-empty-sub">可以帮你检索标讯、统计数量，也能回答招投标相关问题</p>
            <div class="ai-sugs">
              <button v-for="s in SUGGESTIONS" :key="s" class="ai-sug" @click="send(s)">
                {{ s }}
              </button>
            </div>
          </div>

          <!-- 消息列表 -->
          <template v-for="(m, i) in msgs" :key="i">
            <div v-if="m.truncated" class="ai-truncated">较早的对话内容已省略</div>
            <div class="ai-msg" :class="m.role">
              <div
                class="ai-bubble"
                :class="m.role"
                v-html="renderMd(m.content)"
              ></div>

              <!-- 检索结果卡片 -->
              <div v-if="m.results?.length" class="ai-results">
                <div
                  v-for="r in m.results"
                  :key="r.id"
                  class="ai-rcard"
                  @click="goBid(r.id)"
                >
                  <div class="rc-top">
                    <span class="rc-title">{{ r.title }}</span>
                    <span v-if="r.score != null" class="rc-score">{{ r.score }}</span>
                  </div>
                  <div class="rc-meta">
                    <span v-if="r.publish_time">{{ r.publish_time }}</span>
                    <span v-if="r.budget">预算 {{ r.budget }}</span>
                    <span v-if="r.tenderee">{{ r.tenderee }}</span>
                  </div>
                  <div v-if="r.reason" class="rc-reason">{{ r.reason }}</div>
                </div>
                <button class="ai-viewall" @click="viewAll(m)">
                  查看全部结果 <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          </template>

          <!-- 加载态 -->
          <div v-if="loading" class="ai-msg assistant">
            <div class="ai-bubble assistant ai-loading">
              <span class="ai-dots"><i></i><i></i><i></i></span>
              <span class="ai-loading-text">{{ loadingText }}</span>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="aipanel-input">
          <el-input
            v-model="input"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 4 }"
            placeholder="问点什么，Enter 发送（Shift+Enter 换行）"
            :disabled="loading"
            @keydown="onKeydown"
          />
          <button
            class="ai-send"
            :disabled="loading || !input.trim()"
            title="发送"
            @click="send()"
          >
            <el-icon :size="18"><Promotion /></el-icon>
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.aiball-root { position: relative; z-index: 2500; }

/* ===== 悬浮球 ===== */
.aiball {
  position: fixed;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: pointer;
  user-select: none;
  touch-action: none;
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.45), 0 2px 6px rgba(2, 132, 199, 0.35);
  transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
  z-index: 2501;
}
.aiball:hover {
  transform: scale(1.08);
  box-shadow: 0 10px 30px rgba(56, 189, 248, 0.55);
}
.aiball.open { transform: scale(0.94); }
.aiball-ring {
  position: absolute;
  inset: -5px;
  border-radius: 50%;
  border: 2px solid var(--accent-glow);
  animation: aiball-pulse 2.4s var(--ease) infinite;
  pointer-events: none;
}
@keyframes aiball-pulse {
  0% { transform: scale(0.9); opacity: 0.9; }
  70% { transform: scale(1.25); opacity: 0; }
  100% { transform: scale(1.25); opacity: 0; }
}

/* ===== 面板 ===== */
.aipanel {
  position: fixed;
  width: 380px;
  height: min(560px, calc(100vh - 120px));
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: 0 24px 64px rgba(4, 10, 20, 0.28), 0 4px 16px rgba(4, 10, 20, 0.14);
  overflow: hidden;
  z-index: 2500;
}
.aipanel-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: linear-gradient(135deg, var(--brand-900), var(--brand-800));
  color: var(--on-dark);
  cursor: move;
  touch-action: none;
  user-select: none;
  flex-shrink: 0;
}
.hd-left { display: flex; align-items: center; gap: 10px; }
.hd-icon {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-cyan);
}
.hd-title { display: flex; flex-direction: column; line-height: 1.25; }
.hd-title b { font-size: 14px; letter-spacing: 0.02em; }
.hd-title span { font-size: 11px; color: var(--on-dark-mute); }
.hd-acts { display: flex; gap: 6px; }
.hd-btn {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 8px;
  background: rgba(255, 255, 255, 0.08);
  color: var(--on-dark-soft);
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.hd-btn:hover { background: rgba(255, 255, 255, 0.18); color: #fff; }

/* ---- 消息区 ---- */
.aipanel-body {
  flex: 1;
  overflow-y: auto;
  padding: 14px;
  background: var(--surface-soft);
}
.aipanel-body::-webkit-scrollbar { width: 6px; }
.aipanel-body::-webkit-scrollbar-thumb {
  background: var(--line-strong);
  border-radius: 3px;
}

.ai-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 10px 20px;
}
.ai-empty-icon {
  width: 56px; height: 56px;
  display: flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-strong);
  margin-bottom: 12px;
}
.ai-empty-title { margin: 0 0 4px; font-size: 15px; font-weight: 600; color: var(--ink-900); }
.ai-empty-sub { margin: 0 0 18px; font-size: 12px; color: var(--ink-500); line-height: 1.6; }
.ai-sugs { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.ai-sug {
  padding: 9px 12px;
  font-size: 12.5px;
  color: var(--ink-700);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}
.ai-sug:hover {
  border-color: var(--accent-line);
  color: var(--accent-deep);
  background: var(--accent-soft);
}

.ai-truncated {
  text-align: center;
  font-size: 11px;
  color: var(--ink-400);
  margin: 6px 0 10px;
}

.ai-msg { display: flex; flex-direction: column; margin-bottom: 12px; }
.ai-msg.user { align-items: flex-end; }
.ai-msg.assistant { align-items: flex-start; }

.ai-bubble {
  max-width: 86%;
  padding: 9px 12px;
  font-size: 13px;
  line-height: 1.65;
  border-radius: 12px;
  word-break: break-word;
}
.ai-bubble :deep(p) { margin: 0 0 6px; }
.ai-bubble :deep(p:last-child) { margin-bottom: 0; }
.ai-bubble :deep(ul), .ai-bubble :deep(ol) { margin: 4px 0; padding-left: 18px; }
.ai-bubble :deep(li) { margin: 2px 0; }
.ai-bubble :deep(strong) { font-weight: 700; }
.ai-bubble :deep(code) {
  background: rgba(14, 165, 233, 0.12);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 12px;
}
.ai-bubble :deep(.md-h) { font-weight: 700; font-size: 13.5px; }

.ai-bubble.user {
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  color: #fff;
  border-bottom-right-radius: 4px;
}
.ai-bubble.assistant {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-800);
  border-bottom-left-radius: 4px;
}

.ai-loading { display: flex; align-items: center; gap: 8px; }
.ai-loading-text { font-size: 12.5px; color: var(--ink-500); }
.ai-dots { display: inline-flex; gap: 3px; }
.ai-dots i {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: var(--accent-strong);
  animation: ai-dot 1.2s infinite ease-in-out;
}
.ai-dots i:nth-child(2) { animation-delay: 0.18s; }
.ai-dots i:nth-child(3) { animation-delay: 0.36s; }
@keyframes ai-dot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ---- 结果卡片 ---- */
.ai-results {
  width: 86%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.ai-rcard {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}
.ai-rcard:hover {
  border-color: var(--accent-line);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.rc-top { display: flex; align-items: flex-start; gap: 8px; }
.rc-title {
  flex: 1;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-900);
  line-height: 1.5;
}
.rc-score {
  flex-shrink: 0;
  min-width: 30px;
  height: 20px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: #fff;
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  border-radius: 999px;
}
.rc-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: 5px;
  font-size: 11px;
  color: var(--ink-500);
}
.rc-reason {
  margin-top: 5px;
  font-size: 11px;
  color: var(--ink-400);
  line-height: 1.5;
}
.ai-viewall {
  align-self: flex-start;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--accent-deep);
  background: var(--accent-soft);
  border: none;
  border-radius: 999px;
  cursor: pointer;
  transition: background 0.2s;
}
.ai-viewall:hover { background: rgba(56, 189, 248, 0.2); }

/* ---- 输入区 ---- */
.aipanel-input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 10px 12px;
  background: var(--surface);
  border-top: 1px solid var(--line);
  flex-shrink: 0;
}
.aipanel-input :deep(.el-textarea__inner) {
  resize: none;
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.5;
  box-shadow: none;
}
.aipanel-input :deep(.el-textarea__inner:focus) {
  border-color: var(--accent-strong);
  box-shadow: 0 0 0 2px var(--accent-soft);
}
.ai-send {
  width: 36px; height: 36px;
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 10px;
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  color: #fff;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.2s;
}
.ai-send:hover:not(:disabled) { transform: translateY(-1px); }
.ai-send:disabled { opacity: 0.45; cursor: not-allowed; }

/* ---- 面板出现动画 ---- */
.aipanel-enter-active { transition: opacity 0.22s var(--ease), transform 0.22s var(--ease); }
.aipanel-leave-active { transition: opacity 0.16s ease, transform 0.16s ease; }
.aipanel-enter-from, .aipanel-leave-to { opacity: 0; transform: translateY(12px) scale(0.98); }

/* ===== 移动端：底部抽屉 ===== */
@media (max-width: 768px) {
  .aipanel.mobile {
    left: 0 !important;
    right: 0;
    top: auto !important;
    bottom: 0;
    width: 100%;
    height: 74vh;
    border-radius: 18px 18px 0 0;
    border-left: none;
    border-right: none;
    border-bottom: none;
  }
  .aipanel.mobile .aipanel-hd { cursor: default; border-radius: 18px 18px 0 0; }
  .aipanel.mobile .ai-bubble { max-width: 90%; }
  .aipanel.mobile .ai-results { width: 90%; }
  .aiball { width: 50px; height: 50px; }
}
</style>
