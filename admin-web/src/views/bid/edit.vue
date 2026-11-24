<template>
  <div class="page-container">
    <div class="page-card">
      <el-page-header @back="router.back()" :content="isEdit ? '编辑标讯' : '新增标讯'" />
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px" style="margin-top: 20px; max-width: 960px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" maxlength="500" show-word-limit />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目编号"><el-input v-model="form.project_code" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采购人"><el-input v-model="form.tenderee" /></el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="公告类型">
            <el-select v-model="form.notice_type_id" placeholder="请选择" style="width: 100%">
              <el-option v-for="t in noticeTypes" :key="t.id" :label="t.name" :value="t.id" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="8"><el-form-item label="地区代码"><el-input v-model="form.region_code" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="预算"><el-input v-model="form.budget" placeholder="如 100 万元" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="公告发布时间">
            <el-date-picker v-model="form.publish_time" type="datetime" placeholder="选择时间" style="width: 100%" />
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item label="投标截止时间">
            <el-date-picker v-model="form.deadline" type="datetime" placeholder="选择时间" style="width: 100%" />
          </el-form-item></el-col>
        </el-row>
        <el-divider content-position="left">中标信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="中标单位"><el-input v-model="form.winner_unit" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="中标金额"><el-input v-model="form.win_amount" placeholder="如 500000.00" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="招采类型"><el-input v-model="form.procure_type" placeholder="如 公开招标" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="客群"><el-input v-model="form.customer_group" placeholder="如 政务/国企" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="中标时间">
            <el-date-picker v-model="form.winner_publish_time" type="datetime" placeholder="选择时间" style="width: 100%" />
          </el-form-item></el-col>
        </el-row>
        <el-form-item label="公告正文">
          <el-input v-model="form.content" type="textarea" :rows="10" placeholder="支持粘贴 HTML 或纯文本" />
        </el-form-item>
        <el-form-item label="原文链接"><el-input v-model="form.source_url" /></el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="saving" @click="onSubmit">保存</el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { fetchBidDetail, createBid, updateBid, fetchNoticeTypes } from '@/api'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const formRef = ref<FormInstance>()
const saving = ref(false)
const noticeTypes = ref<any[]>([])

const isEdit = computed(() => !!route.params.id)
const form = reactive<any>({
  title: '', project_code: '', tenderee: '', agency: '', notice_type_id: null,
  region_code: '', publish_time: null, deadline: null, budget: '',
  winner_unit: '', win_amount: '', procure_type: '', customer_group: '',
  winner_publish_time: null, content: '', source_url: '',
})

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
}

async function onSubmit() {
  await formRef.value?.validate()
  saving.value = true
  try {
    const payload = { ...form }
    // dayjs → ISO string
    ;['publish_time', 'deadline', 'winner_publish_time'].forEach((k) => {
      if (payload[k] && typeof payload[k] !== 'string') {
        payload[k] = dayjs(payload[k]).toISOString()
      }
    })
    if (isEdit.value) {
      payload.id = Number(route.params.id)
      await updateBid(payload)
      ElMessage.success('更新成功')
    } else {
      await createBid(payload)
      ElMessage.success('创建成功')
    }
    router.replace('/bid/list')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  noticeTypes.value = await fetchNoticeTypes()
  if (isEdit.value) {
    const detail = await fetchBidDetail(Number(route.params.id))
    Object.assign(form, detail)
  }
})
</script>
