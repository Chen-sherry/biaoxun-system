<template>
  <div class="nf-page">
    <el-result icon="warning" title="页面走丢了" sub-title="请检查地址，或返回首页">
      <template #extra>
        <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.nf-page { min-height: 50vh; display: flex; align-items: center; justify-content: center; }
</style>
