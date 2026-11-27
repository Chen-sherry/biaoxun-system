<template>
  <div class="page-container">
    <div class="page-card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h3 class="card-title">会员套餐管理</h3>
        <el-button type="primary" @click="openDialog()">新增套餐</el-button>
      </div>
      <el-table :data="list" v-loading="loading" stripe style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="套餐名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="code" label="编码" width="100" />
        <el-table-column prop="level" label="等级" width="70" />
        <el-table-column prop="price" label="原价" width="90">
          <template #default="{ row }">{{ row.price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="sale_price" label="售价" width="90">
          <template #default="{ row }">{{ row.sale_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column prop="duration_days" label="天数" width="70" />
        <el-table-column prop="max_subscribe" label="订阅上限" width="90" />
        <el-table-column prop="allow_export" label="允许导出" width="90">
          <template #default="{ row }">
            <el-tag :type="row.allow_export ? 'success' : 'info'" size="small">{{ row.allow_export ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="allow_contact" label="联系方式" width="90">
          <template #default="{ row }">
            <el-tag :type="row.allow_contact ? 'success' : 'info'" size="small">{{ row.allow_contact ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="70" />
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'info'" size="small">{{ row.status ? '上架' : '下架' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button link :type="row.status ? 'warning' : 'success'" @click="toggleStatus(row)">
              {{ row.status ? '下架' : '上架' }}
            </el-button>
            <el-popconfirm title="确定删除该套餐？" @confirm="remove(row)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="total > pageSize"
        style="margin-top: 12px; justify-content: flex-end"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        v-model:current-page="page"
        @current-change="loadData"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑套餐' : '新增套餐'" width="580px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="110px">
        <el-form-item label="套餐名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="套餐编码" prop="code"><el-input v-model="form.code" :disabled="!!editing?.id" /></el-form-item>
        <el-form-item label="原价(元)" prop="price"><el-input-number v-model="form.price" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="售价(元)" prop="sale_price"><el-input-number v-model="form.sale_price" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="有效天数" prop="duration_days"><el-input-number v-model="form.duration_days" :min="1" /></el-form-item>
        <el-form-item label="等级" prop="level">
          <el-select v-model="form.level">
            <el-option :label="'等级 ' + i" :value="i" v-for="i in 5" :key="i" />
          </el-select>
        </el-form-item>
        <el-form-item label="订阅上限" prop="max_subscribe"><el-input-number v-model="form.max_subscribe" :min="0" /></el-form-item>
        <el-form-item label="允许导出">
          <el-switch v-model="form.allow_export" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="可见联系方式">
          <el-switch v-model="form.allow_contact" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="排序" prop="sort"><el-input-number v-model="form.sort" :min="0" /></el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { fetchAdminPackageList, createPackage, updatePackage, deletePackage } from '@/api'

const loading = ref(false)
const saving = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const dialogVisible = ref(false)
const editing = ref<any>(null)
const formRef = ref<FormInstance>()

const defaultForm = {
  name: '', code: '', price: 0, sale_price: 0, duration_days: 365,
  level: 1, max_subscribe: 20, allow_export: 1, allow_contact: 1,
  sort: 0, status: 1, description: '',
}
const form = reactive({ ...defaultForm })

const rules: FormRules = {
  name: [{ required: true, message: '请输入套餐名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入套餐编码', trigger: 'blur' }],
  price: [{ required: true, message: '请输入原价', trigger: 'blur' }],
  sale_price: [{ required: true, message: '请输入售价', trigger: 'blur' }],
  duration_days: [{ required: true, message: '请输入有效天数', trigger: 'blur' }],
}

async function loadData() {
  loading.value = true
  try {
    const res = await fetchAdminPackageList({ page: page.value, page_size: pageSize })
    list.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

function openDialog(row?: any) {
  editing.value = row || null
  Object.assign(form, row ? { ...row } : { ...defaultForm })
  dialogVisible.value = true
}

async function save() {
  await formRef.value?.validate()
  saving.value = true
  try {
    if (editing.value?.id) {
      await updatePackage(editing.value.id, form)
    } else {
      await createPackage(form)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    loadData()
  } finally { saving.value = false }
}

async function toggleStatus(row: any) {
  await updatePackage(row.id, { status: row.status ? 0 : 1 })
  ElMessage.success(row.status ? '已下架' : '已上架')
  loadData()
}

async function remove(row: any) {
  try {
    await deletePackage(row.id)
    ElMessage.success('删除成功')
    loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.card-title { margin: 0; font-size: 16px; }
</style>
