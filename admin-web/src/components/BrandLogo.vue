<script setup lang="ts">
import logoMark from '@/assets/brand/logo-mark.svg'

withDefaults(defineProps<{
  size?: number | string
  showText?: boolean
  text?: string
  textSize?: number
  light?: boolean
}>(), {
  size: 34,
  showText: true,
  text: '标讯速递',
  textSize: 20,
  light: false,
})
</script>

<template>
  <span class="brand-logo" :class="{ 'is-light': light }">
    <img class="brand-logo__mark" :src="logoMark" :style="{ width: size + 'px', height: size + 'px' }" alt="" />
    <span v-if="showText" class="brand-logo__text" :style="{ fontSize: textSize + 'px' }">{{ text }}</span>
  </span>
</template>

<style scoped>
.brand-logo { display: inline-flex; align-items: center; gap: 10px; line-height: 1; }
.brand-logo__mark { display: block; flex: none; filter: drop-shadow(0 0 8px rgba(56, 189, 248, 0.35)); }
.brand-logo__text {
  font-weight: 800;
  letter-spacing: 0.5px;
  white-space: nowrap;
  background: linear-gradient(135deg, #e8f2ff 0%, #7dd3fc 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.brand-logo:not(.is-light) .brand-logo__text {
  background: linear-gradient(135deg, #0b1b2e 0%, #0284c7 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
</style>
