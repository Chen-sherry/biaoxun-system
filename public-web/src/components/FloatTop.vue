<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Top } from '@element-plus/icons-vue'

const visible = ref(false)
let ticking = false

function onScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    const y = window.scrollY
    // 滚过 300px 才出现，直到接近顶部才隐藏
    if (y > 300) visible.value = true
    else if (y < 150) visible.value = false
    ticking = false
  })
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <transition name="ftop">
    <div
      v-if="visible"
      class="float-top"
      title="回顶部"
      @click="scrollToTop"
    >
      <el-icon :size="22"><Top /></el-icon>
    </div>
  </transition>
</template>

<style scoped>
.float-top {
  position: fixed;
  right: 12px;
  bottom: 96px;
  width: 46px; height: 46px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; cursor: pointer; user-select: none;
  background: var(--surface);
  border: 1px solid var(--line);
  box-shadow: 0 4px 16px rgba(2, 6, 23, 0.12);
  transition: transform 0.2s var(--ease), box-shadow 0.2s var(--ease), background 0.2s;
  z-index: 2499;
}
.float-top :deep(.el-icon) { color: var(--ink-500); }
.float-top:hover {
  background: var(--accent-strong);
  border-color: var(--accent-strong);
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(14, 165, 233, 0.35);
}
.float-top:hover :deep(.el-icon) { color: #fff; }

.ftop-enter-active, .ftop-leave-active { transition: opacity 0.2s var(--ease), transform 0.2s var(--ease); }
.ftop-enter-from, .ftop-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 768px) {
  .float-top { right: 8px; bottom: 84px; }
}
</style>
