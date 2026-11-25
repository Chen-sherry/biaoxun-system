// 轻量 markdown 渲染（模拟企业微信 markdown 支持的语法子集）：
// ## 标题 / **加粗** / [文字](链接) / > 引用 / - 列表 / 换行
// 不引入第三方依赖，仅用于后台预览

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function mdLite(src: string): string {
  const lines = escapeHtml(src || '').split('\n')
  const out: string[] = []
  let inList = false

  const inline = (s: string) =>
    s
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')

  for (const raw of lines) {
    const line = raw.trimEnd()
    if (/^-\s+/.test(line)) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push(`<li>${inline(line.replace(/^-\s+/, ''))}</li>`)
      continue
    }
    if (inList) { out.push('</ul>'); inList = false }
    if (/^##\s+/.test(line)) {
      out.push(`<div class="md-h">${inline(line.replace(/^##\s+/, ''))}</div>`)
    } else if (/^&gt;\s?/.test(line)) {
      out.push(`<div class="md-quote">${inline(line.replace(/^&gt;\s?/, ''))}</div>`)
    } else if (line === '') {
      out.push('<div class="md-gap"></div>')
    } else {
      out.push(`<div class="md-p">${inline(line)}</div>`)
    }
  }
  if (inList) out.push('</ul>')
  return out.join('')
}
