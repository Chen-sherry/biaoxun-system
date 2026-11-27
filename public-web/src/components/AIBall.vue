<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Close, Delete, Promotion, MagicStick, Warning, RefreshRight } from '@element-plus/icons-vue'

// ============================================================
// AI 悬浮球（P2 多轮对话 v2：流式 SSE + 交互增强）
// - 右下角常驻可拖拽球体，点击展开对话面板（面板标题栏也可拖动）
// - 登录 / 会员购买页隐藏；会话 localStorage 持久化（上限 200 条）
// - 流式：/ai/chat/stream SSE，逐字打字 + 状态事件 + tools 先到再回答
// - 失败气泡可重试；清空二次确认；链接/表格/代码块 Markdown；快捷提问 chips
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
  notice_type?: string
}
interface Msg {
  role: 'user' | 'assistant'
  content: string
  results?: BidResult[]
  query?: string
  truncated?: boolean
  ts?: number           // 消息创建时间戳（ms）
  streaming?: boolean   // 正在流式生成
  error?: boolean       // 失败态
}

const open = ref(false)
const msgs = ref<Msg[]>([])
const input = ref('')
const loading = ref(false)      // 发送前置状态（含等待连接中）
const chatEnabled = ref(true)
const msgsBox = ref<HTMLElement | null>(null)
const streamingIdx = ref(-1)    // 正在流式生成的 assistant 气泡 index（-1=无）

// ---- 持久化 ----
const MSG_KEY = 'biaoxun_ai_chat'
const BALL_KEY = 'biaoxun_ai_ball_pos'
const PANEL_KEY = 'biaoxun_ai_panel_pos'
const MAX_MSGS = 200

function saveMsgs() {
  const out = msgs.value
    .filter(m => !m.streaming)   // 流式中的气泡不落盘
    .map(({ role, content, results, query, truncated, ts, error }) => ({
      role, content, results, query, truncated, ts, error,
    }))
  if (out.length > MAX_MSGS) {
    out.splice(0, out.length - MAX_MSGS)
  }
  try { localStorage.setItem(MSG_KEY, JSON.stringify(out)) } catch { /* 忽略 */ }
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
    } else { togglePanel() }
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
    try { el.releasePointerCapture(ev.pointerId) } catch { /* 忽略 */ }
    try { localStorage.setItem(PANEL_KEY, JSON.stringify(panelPos.value)) } catch { /* 忽略 */ }
  }
  el.addEventListener('pointermove', move)
  el.addEventListener('pointerup', up)
}
const panelStyle = computed(() =>
  isMobile.value ? {} : { left: panelPos.value.x + 'px', top: panelPos.value.y + 'px' })

// ---- Markdown 渲染增强 ----
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}
function inlineFmt(t: string): string {
  return t
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    // 链接：[文本](url) 仅放行 http/https
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
}
function renderMd(src: string): string {
  const raw = src || ''
  if (!raw) return ''
  // 先把 ``` 围栏代码块整体替换成占位符（escape 后不参与下面的行解析）
  const codeBlocks: string[] = []
  let s = raw.replace(/```(\w*)\n?([\s\S]*?)```/g, (_m, lang, body) => {
    const escaped = escapeHtml(body.trimEnd())
    codeBlocks.push(`<pre class="md-code"><code class="md-code-inner">${escaped}</code></pre>`)
    return `\u0000CODE${codeBlocks.length - 1}\u0000`
  })
  const lines = s.split(/\r?\n/)
  const out: string[] = []
  let list: 'ul' | 'ol' | null = null
  let para: string[] = []
  let table: string[] = []
  let inTable = false

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${inlineFmt(para.join('<br>'))}</p>`); para = []
    }
  }
  const closeList = () => {
    if (list) { out.push(list === 'ul' ? '</ul>' : '</ol>'); list = null }
  }
  const closeTable = () => {
    if (!inTable) return
    inTable = false
    if (table.length >= 2) {
      const [hdr, sep, ...rows] = table
      const isHdr = /^[\s|:-]+$/.test(sep)
      const makeRow = (cells: string[]) =>
        '<tr>' + cells.map(c => `<td>${inlineFmt(c.trim())}</td>`).join('') + '</tr>'
      const hdrCells = hdr.split('|').filter((_, i, a) =>
        !(i === 0 && !a[0].trim()) && !(i === a.length - 1 && !a[i].trim()))
      out.push('<table class="md-table"><thead>')
      out.push('<tr>' + hdrCells.map(c => `<th>${inlineFmt(c.trim())}</th>`).join('') + '</tr>')
      out.push('</thead><tbody>')
      if (isHdr) {
        // 跳过分隔行
        for (const r of rows) {
          const cells = r.split('|').filter((_, i, a) =>
            !(i === 0 && !a[0].trim()) && !(i === a.length - 1 && !a[i].trim()))
          out.push(makeRow(cells))
        }
      } else {
        // 无分隔行，全部当 body
        for (const r of [sep, ...rows]) {
          const cells = r.split('|').filter((_, i, a) =>
            !(i === 0 && !a[0].trim()) && !(i === a.length - 1 && !a[i].trim()))
          out.push(makeRow(cells))
        }
      }
      out.push('</tbody></table>')
    }
    table = []
  }

  for (const rawLine of lines) {
    // 占位符还原
    if (rawLine.includes('\u0000CODE')) {
      const idx = parseInt(rawLine.match(/CODE(\d+)/)?.[1] || '-1', 10)
      if (!isNaN(idx) && idx >= 0) {
        flushPara(); closeList(); closeTable()
        out.push(codeBlocks[idx])
        continue
      }
    }
    const line = escapeHtml(rawLine)
    const isTableRow = /\|/.test(line.trim()) && !/^\s*[-*]\s/.test(rawLine)
    if (isTableRow && !rawLine.trim().startsWith('#')) {
      if (!inTable) { flushPara(); closeList(); inTable = true; table = [] }
      table.push(line)
      continue
    } else if (inTable) {
      closeTable()
    }

    const ul = rawLine.match(/^\s*[-*+]\s+(.*)$/)
    const ol = rawLine.match(/^\s*\d+[.、)]\s+(.*)$/)
    const h = rawLine.match(/^#{1,4}\s+(.*)$/)
    if (ul || ol) {
      flushPara(); closeTable()
      const kind: 'ul' | 'ol' = ul ? 'ul' : 'ol'
      if (list !== kind) { closeList(); out.push(`<${kind}>`); list = kind }
      out.push(`<li>${inlineFmt((ul || ol)![1])}</li>`)
    } else if (h) {
      flushPara(); closeList(); closeTable()
      out.push(`<p class="md-h">${inlineFmt(h[1])}</p>`)
    } else if (!rawLine.trim()) {
      flushPara(); closeList(); closeTable()
    } else {
      closeList(); closeTable()
      para.push(line)
    }
  }
  flushPara(); closeList(); closeTable()
  // 还原残留占位符
  return out.join('').replace(/\u0000CODE\d+\u0000/g, '')
}

// ---- 滚动跟随（消息变化 + 流式内容追加）----
function scrollBottom() {
  nextTick(() => {
    if (msgsBox.value) msgsBox.value.scrollTop = msgsBox.value.scrollHeight
  })
}
watch(() => [msgs.value.length,
  msgs.value[streamingIdx.value]?.content?.length || 0],
  scrollBottom)
watch(open, (v) => { if (v) scrollBottom() })

// ---- 会员提示 ----
async function memberGate() {
  try {
    await ElMessageBox.alert(
      'AI 助手是付费会员专属功能，开通会员后即可使用。',
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

function fmtTime(ts?: number) {
  if (!ts) return ''
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ---- SSE 解析 ----
async function readSSE(response: Response, onEvent: (ev: any) => void) {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder('utf-8')
  let buf = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx: number
    // 按 \n\n 分帧
    while ((idx = buf.indexOf('\n\n')) !== -1) {
      const chunk = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      const lines = chunk.split('\n').filter(l => l.startsWith('data:'))
      for (const ln of lines) {
        const payload = ln.slice(5).trim()
        if (!payload || payload === '[DONE]') continue
        try { onEvent(JSON.parse(payload)) } catch { /* 忽略坏帧 */ }
      }
    }
  }
  if (buf.trim()) {
    for (const ln of buf.split('\n').filter(l => l.startsWith('data:'))) {
      const payload = ln.slice(5).trim()
      if (!payload || payload === '[DONE]') continue
      try { onEvent(JSON.parse(payload)) } catch { /* 忽略 */ }
    }
  }
}

// ---- 发送（流式 fetch）----
async function send(preset?: string, retryOf?: Msg) {
  const q = (preset ?? input.value).trim()
  if (!q || loading.value) return
  if (!chatEnabled.value) { ElMessage.info('AI 助手暂未开放'); return }

  // 失败重试：替换掉原来的错误气泡内容
  if (retryOf) {
    const idx = msgs.value.indexOf(retryOf)
    if (idx === -1) return
    // 把错误气泡重置成空 content，等待新流式
    retryOf.content = ''
    retryOf.error = false
    retryOf.streaming = true
    retryOf.ts = retryOf.ts || Date.now()
    streamingIdx.value = idx
  } else {
    input.value = ''
    msgs.value.push({ role: 'user', content: q, ts: Date.now() })
    saveMsgs()
    msgs.value.push({ role: 'assistant', content: '', ts: Date.now(), streaming: true })
    streamingIdx.value = msgs.value.length - 1
  }
  scrollBottom()
  loading.value = true

  const token = localStorage.getItem('token') || ''
  const assistantIdx = streamingIdx.value

  try {
    const response = await fetch(`${API}/api/v1/ai/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        messages: msgs.value
          .filter(m => !m.streaming)
          .map(m => ({ role: m.role, content: m.content })),
        inject_context: true,
      }),
    })

    if (!response.ok) {
      let body = ''
      try { body = await response.text() } catch { /* 忽略 */ }
      const status = response.status
      if (status === 401 || status === 403) {
        // 失败了，去掉正在流式的气泡
        msgs.value.splice(assistantIdx, 1)
        // 也去掉刚才 push 的 user 气泡（第一次发送时）
        if (!retryOf) {
          const userIdx = assistantIdx - 1
          if (userIdx >= 0 && msgs.value[userIdx]?.role === 'user') {
            msgs.value.splice(userIdx, 1)
          }
        }
        saveMsgs()
        await memberGate()
        return
      }
      if (status === 429) {
        markAssistantError(assistantIdx, '今日 AI 对话次数已达上限，请明天再来')
        return
      }
      markAssistantError(assistantIdx, `⚠️ 请求失败（HTTP ${status}）`)
      return
    }

    await readSSE(response, (ev) => {
      const a = msgs.value[assistantIdx]
      if (!a) return
      if (ev.type === 'delta') {
        a.content += ev.text || ''
      } else if (ev.type === 'status') {
        // 可用于 loading 提示，但已流式中就不展示
      } else if (ev.type === 'results') {
        if (Array.isArray(ev.results)) {
          a.results = ev.results as BidResult[]
          if (!a.query) a.query = q
        }
      } else if (ev.type === 'done') {
        a.streaming = false
        if (a.results === undefined && Array.isArray(ev.results)) {
          a.results = ev.results as BidResult[]
        }
        if (ev.truncated) a.truncated = true
        if (ev.reply && (!a.content || a.content.length < ev.reply.length)) {
          // 兜底：如果流式 content 短于后端 reply（应该不会发生），补齐
          a.content = ev.reply
        }
        saveMsgs()
        streamingIdx.value = -1
      } else if (ev.type === 'error') {
        a.streaming = false
        markAssistantError(assistantIdx, `⚠️ ${ev.message || 'AI 出错了'}`)
      }
    })

    // 流没正常结束（done 事件丢失）：兜底
    const a = msgs.value[assistantIdx]
    if (a && a.streaming) {
      a.streaming = false
      if (!a.content) markAssistantError(assistantIdx, '⚠️ AI 未返回内容，请重试')
      saveMsgs()
    }
  } catch (e: any) {
    if (e?.name === 'AbortError') return
    markAssistantError(assistantIdx, '⚠️ AI 暂时不可用，请检查网络后重试')
  } finally {
    loading.value = false
    scrollBottom()
  }
}

function markAssistantError(idx: number, msg: string) {
  const a = msgs.value[idx]
  if (!a) return
  a.streaming = false
  a.error = true
  a.content = msg
  streamingIdx.value = -1
  saveMsgs()
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
async function clearMsgs() {
  try {
    await ElMessageBox.confirm(
      '确定要清空全部会话历史吗？此操作不可恢复。',
      '清空会话',
      {
        type: 'warning',
        confirmButtonText: '清空',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
        center: true,
      },
    )
  } catch { return }
  msgs.value = []
  streamingIdx.value = -1
  try { localStorage.removeItem(MSG_KEY) } catch { /* 忽略 */ }
  ElMessage.success('已清空会话')
}
function goBid(id: number) { router.push(`/bid/${id}`); closePanel() }
function viewAll(m: Msg) {
  const kw = (m.query || '').trim()
  router.push(kw ? `/ai-match?kw=${encodeURIComponent(kw)}` : '/ai-match')
  closePanel()
}
function retryMsg(m: Msg) { send(undefined, m) }

// 快捷提问
const SUGGESTIONS = [
  '帮我找合肥最近一个月的学校招标',
  '最近新增多少条标讯',
  '招标公告和中标公告有什么区别',
]

// ---- 初始化 ----
function onResize() {
  isMobile.value = window.innerWidth <= 768
  clampBall(); clampPanel()
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
  window.addEventListener('orientationchange', onResize)

  try {
    const res = await fetch(`${API}/api/v1/ai/config`)
    const d = await res.json()
    if (d?.code === 0) chatEnabled.value = !!d.data?.chat_enabled
  } catch { /* 保持可用 */ }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('orientationchange', onResize)
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
      <div v-if="open" class="aipanel" :class="{ mobile: isMobile }" :style="panelStyle">
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
            <p class="ai-empty-sub">检索标讯、统计数量、解读公告，也能回答招投标相关问题</p>
            <div class="ai-sugs">
              <button v-for="s in SUGGESTIONS" :key="s" class="ai-sug" @click="send(s)">
                {{ s }}
              </button>
            </div>
          </div>

          <!-- 消息列表 -->
          <template v-for="(m, i) in msgs" :key="i">
            <div v-if="m.truncated" class="ai-truncated">较早的对话内容已省略</div>
            <div class="ai-msg" :class="[m.role, { error: m.error }]">
              <div
                class="ai-bubble"
                :class="[m.role, { 'streaming': m.streaming, 'err': m.error }]"
                v-html="renderMd(m.content)"
              ></div>
              <span v-if="m.streaming && !m.content" class="ai-stream-ph">AI 思考中…</span>
              <span v-else-if="m.streaming" class="ai-cursor" aria-hidden="true">▍</span>

              <!-- 时间戳 + 重试 -->
              <div v-if="(m.ts || m.error) && !m.streaming" class="ai-meta-line">
                <span v-if="m.ts" class="ai-ts">{{ fmtTime(m.ts) }}</span>
                <button v-if="m.error" class="ai-retry" @click="retryMsg(m)">
                  <el-icon><RefreshRight /></el-icon> 重试
                </button>
              </div>

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
                    <span v-if="r.notice_type" class="rc-tag">{{ r.notice_type }}</span>
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
        </div>

        <!-- 输入区 -->
        <div class="aipanel-input-wrap">
          <!-- 快捷 chips（仅面板打开 + 空输入 + 有历史时） -->
          <div
            v-if="msgs.length && !input.trim() && !loading"
            class="ai-chips"
          >
            <button
              v-for="s in SUGGESTIONS"
              :key="s"
              class="ai-chip"
              @click="input = s"
            >{{ s }}</button>
          </div>
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
      </div>
    </transition>
  </div>
</template>

<style scoped>
.aiball-root { position: relative; z-index: 2500; }

/* ===== 悬浮球 ===== */
.aiball {
  position: fixed;
  width: 56px; height: 56px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; cursor: pointer; user-select: none; touch-action: none;
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  box-shadow: 0 8px 24px rgba(14, 165, 233, 0.45), 0 2px 6px rgba(2, 132, 199, 0.35);
  transition: transform 0.25s var(--ease), box-shadow 0.25s var(--ease);
  z-index: 2501;
}
.aiball:hover { transform: scale(1.08); box-shadow: 0 10px 30px rgba(56, 189, 248, 0.55); }
.aiball.open { transform: scale(0.94); }
.aiball-ring {
  position: absolute; inset: -5px; border-radius: 50%;
  border: 2px solid var(--accent-glow);
  animation: aiball-pulse 2.4s var(--ease) infinite; pointer-events: none;
}
@keyframes aiball-pulse {
  0% { transform: scale(0.9); opacity: 0.9; }
  70% { transform: scale(1.25); opacity: 0; }
  100% { transform: scale(1.25); opacity: 0; }
}

/* ===== 面板 ===== */
.aipanel {
  position: fixed; width: 380px; height: min(560px, calc(100vh - 120px));
  display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: 0 24px 64px rgba(4, 10, 20, 0.28), 0 4px 16px rgba(4, 10, 20, 0.14);
  overflow: hidden; z-index: 2500;
}
.aipanel-hd {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px;
  background: linear-gradient(135deg, var(--brand-900), var(--brand-800));
  color: var(--on-dark); cursor: move; touch-action: none; user-select: none; flex-shrink: 0;
}
.hd-left { display: flex; align-items: center; gap: 10px; }
.hd-icon {
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  border-radius: 50%; background: var(--accent-soft); color: var(--accent-cyan);
}
.hd-title { display: flex; flex-direction: column; line-height: 1.25; }
.hd-title b { font-size: 14px; letter-spacing: 0.02em; }
.hd-title span { font-size: 11px; color: var(--on-dark-mute); }
.hd-acts { display: flex; gap: 6px; }
.hd-btn {
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 8px;
  background: rgba(255, 255, 255, 0.08); color: var(--on-dark-soft); cursor: pointer;
  transition: background 0.2s, color 0.2s;
}
.hd-btn:hover { background: rgba(255, 255, 255, 0.18); color: #fff; }

/* ---- 消息区 ---- */
.aipanel-body {
  flex: 1; overflow-y: auto; padding: 14px; background: var(--surface-soft);
}
.aipanel-body::-webkit-scrollbar { width: 6px; }
.aipanel-body::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 3px; }

.ai-empty { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 40px 10px 20px; }
.ai-empty-icon { width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; border-radius: 50%; background: var(--accent-soft); color: var(--accent-strong); margin-bottom: 12px; }
.ai-empty-title { margin: 0 0 4px; font-size: 15px; font-weight: 600; color: var(--ink-900); }
.ai-empty-sub { margin: 0 0 18px; font-size: 12px; color: var(--ink-500); line-height: 1.6; }
.ai-sugs { display: flex; flex-direction: column; gap: 8px; width: 100%; }
.ai-sug {
  padding: 9px 12px; font-size: 12.5px; color: var(--ink-700);
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  cursor: pointer; text-align: left;
  transition: border-color 0.2s, color 0.2s, background 0.2s;
}
.ai-sug:hover { border-color: var(--accent-line); color: var(--accent-deep); background: var(--accent-soft); }

.ai-truncated { text-align: center; font-size: 11px; color: var(--ink-400); margin: 6px 0 10px; }

.ai-msg { display: flex; flex-direction: column; margin-bottom: 12px; }
.ai-msg.user { align-items: flex-end; }
.ai-msg.assistant { align-items: flex-start; }

.ai-bubble {
  max-width: 86%; padding: 9px 12px; font-size: 13px; line-height: 1.65;
  border-radius: 12px; word-break: break-word;
}
.ai-bubble.user {
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  color: #fff; border-bottom-right-radius: 4px;
}
.ai-bubble.assistant {
  background: var(--surface); border: 1px solid var(--line); color: var(--ink-800);
  border-bottom-left-radius: 4px;
}
.ai-bubble.assistant.err { border-color: #fecaca; background: #fef2f2; color: #b91c1c; }
.ai-stream-ph { font-size: 12.5px; color: var(--ink-500); margin-top: 6px; padding: 0 4px; }
.ai-cursor {
  display: inline-block; margin-left: 1px; color: var(--accent-strong);
  animation: ai-blink 0.9s steps(2) infinite; font-weight: 400;
}
@keyframes ai-blink { 50% { opacity: 0; } }

/* meta 行：时间戳 + 重试 */
.ai-meta-line {
  display: flex; gap: 8px; align-items: center; margin-top: 3px;
  padding: 0 4px; font-size: 11px; color: var(--ink-400);
}
.ai-retry {
  display: inline-flex; align-items: center; gap: 3px;
  padding: 2px 8px; border-radius: 999px;
  border: 1px solid #fecaca; background: #fef2f2; color: #b91c1c;
  font-size: 11px; cursor: pointer; transition: background 0.2s;
}
.ai-retry:hover { background: #fee2e2; }

/* Markdown 内部样式 */
.ai-bubble :deep(p) { margin: 0 0 6px; }
.ai-bubble :deep(p:last-child) { margin-bottom: 0; }
.ai-bubble :deep(ul), .ai-bubble :deep(ol) { margin: 4px 0; padding-left: 18px; }
.ai-bubble :deep(li) { margin: 2px 0; }
.ai-bubble :deep(strong) { font-weight: 700; }
.ai-bubble :deep(code) {
  background: rgba(14, 165, 233, 0.12); padding: 1px 5px; border-radius: 4px; font-size: 12px;
}
.ai-bubble :deep(pre.md-code) {
  background: #f8fafc; border: 1px solid var(--line); border-radius: 8px;
  padding: 8px 10px; margin: 6px 0; overflow-x: auto; font-size: 12px; line-height: 1.55;
}
.ai-bubble :deep(pre.md-code code) {
  background: transparent; padding: 0; border-radius: 0; color: var(--ink-800);
}
.ai-bubble :deep(table.md-table) {
  border-collapse: collapse; margin: 6px 0; font-size: 12px; width: 100%;
}
.ai-bubble :deep(table.md-table th), .ai-bubble :deep(table.md-table td) {
  border: 1px solid var(--line); padding: 4px 8px; text-align: left;
}
.ai-bubble :deep(table.md-table th) { background: var(--surface-soft); font-weight: 600; }
.ai-bubble :deep(a) { color: var(--accent-deep); text-decoration: underline; text-underline-offset: 2px; }
.ai-bubble :deep(.md-h) { font-weight: 700; font-size: 13.5px; }

/* ---- 结果卡片 ---- */
.ai-results { width: 86%; display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.ai-rcard {
  background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 10px 12px; cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}
.ai-rcard:hover { border-color: var(--accent-line); box-shadow: var(--shadow-card); transform: translateY(-1px); }
.rc-top { display: flex; align-items: flex-start; gap: 8px; }
.rc-title { flex: 1; font-size: 12.5px; font-weight: 600; color: var(--ink-900); line-height: 1.5; }
.rc-score {
  flex-shrink: 0; min-width: 30px; height: 20px; padding: 0 6px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; font-variant-numeric: tabular-nums; color: #fff;
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  border-radius: 999px;
}
.rc-meta { display: flex; flex-wrap: wrap; gap: 4px 10px; margin-top: 5px; font-size: 11px; color: var(--ink-500); }
.rc-tag {
  padding: 1px 6px; border-radius: 999px;
  background: var(--accent-soft); color: var(--accent-deep); font-weight: 600;
}
.rc-reason { margin-top: 5px; font-size: 11px; color: var(--ink-400); line-height: 1.5; }
.ai-viewall {
  align-self: flex-start; padding: 6px 12px; font-size: 12px; color: var(--accent-deep);
  background: var(--accent-soft); border: none; border-radius: 999px; cursor: pointer;
  transition: background 0.2s;
}
.ai-viewall:hover { background: rgba(56, 189, 248, 0.2); }

/* ---- 输入区 ---- */
.aipanel-input-wrap { display: flex; flex-direction: column; flex-shrink: 0; }
.ai-chips {
  display: flex; gap: 6px; padding: 6px 12px 0;
  overflow-x: auto; flex-shrink: 0;
  scrollbar-width: thin;
}
.ai-chips::-webkit-scrollbar { height: 3px; }
.ai-chip {
  flex-shrink: 0; padding: 4px 10px; font-size: 11.5px;
  color: var(--ink-600); background: var(--surface-soft);
  border: 1px solid var(--line); border-radius: 999px; cursor: pointer;
  white-space: nowrap; transition: all 0.2s;
}
.ai-chip:hover { color: var(--accent-deep); border-color: var(--accent-line); background: var(--accent-soft); }

.aipanel-input {
  display: flex; align-items: flex-end; gap: 8px;
  padding: 10px 12px; background: var(--surface); border-top: 1px solid var(--line);
}
.aipanel-input :deep(.el-textarea__inner) {
  resize: none; border-radius: 10px; padding: 8px 12px;
  font-size: 13px; line-height: 1.5; box-shadow: none;
}
.aipanel-input :deep(.el-textarea__inner:focus) {
  border-color: var(--accent-strong); box-shadow: 0 0 0 2px var(--accent-soft);
}
.ai-send {
  width: 36px; height: 36px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  border: none; border-radius: 10px;
  background: linear-gradient(135deg, var(--accent-strong), var(--accent-deep));
  color: #fff; cursor: pointer; transition: opacity 0.2s, transform 0.2s;
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
    left: 0 !important; right: 0; top: auto !important; bottom: 0;
    width: 100%; height: 74vh;
    border-radius: 18px 18px 0 0; border-left: none; border-right: none; border-bottom: none;
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }
  .aipanel.mobile .aipanel-hd { cursor: default; border-radius: 18px 18px 0 0; }
  .aipanel.mobile .ai-bubble { max-width: 92%; }
  .aipanel.mobile .ai-results { width: 92%; }
  .aiball { width: 50px; height: 50px; }
}
</style>
