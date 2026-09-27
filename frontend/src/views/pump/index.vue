<template>
  <section class="page" data-module="pump">
    <header class="page-head">
      <div>
        <h2>泵站运行管理</h2>
        <p class="page-desc">维护水泵机组，围绕机组编号、所属厂站、水泵型号、运行数据做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记水泵机组</button>
        <button class="btn" type="button" @click="exportRows">导出泵站运行清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>机组编号</span>
        <input v-model="keyword" placeholder="按机组编号检索" />
      </label>
      <label class="filter-item">
        <span>机组状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayValue(row, column) }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <template v-if="!isLocked(row)">
              <button class="link" type="button" @click="openRecords(row)">运行记录</button>
              <button
                v-for="action in availableActions(row)"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </template>
            <button v-else class="link" type="button" @click="openRecords(row)">查看运行记录</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无泵站运行数据，可先登记水泵机组</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条泵站运行记录</span>
      <span v-if="message" :class="messageOk ? 'success-text' : 'error-text'">{{ message }}</span>
    </footer>

    <RunRecordModal
      v-if="recordEntryId !== null"
      :entry-id="recordEntryId"
      @close="recordEntryId = null"
      @saved="reload"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import RunRecordModal from './RunRecordModal.vue'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/pump'
const columns = ["机组编号", "所属厂站", "水泵型号", "额定流量", "运行电流", "累计运行时间", "轴承温度", "机组状态"]
const statuses = ["运行", "备用", "故障", "已停机"]
// 不同状态下允许的动作；已停机不在任何分支里，天然只能查看
const ACTIONS_BY_STATUS: Record<string, string[]> = {
  "运行": ["切换备用", "标记故障", "故障停机"],
  "备用": ["启用备用", "故障停机"],
  "故障": ["故障停机", "启用备用"],
}

const router = useRouter()
const rows = ref<Row[]>([])
const total = ref(0)
const message = ref('')
const messageOk = ref(false)
const keyword = ref('')
const statusFilter = ref('')
const recordEntryId = ref<number | null>(null)

const stats = computed(() => {
  const countOf = (status: string) => rows.value.filter((row) => row.status === status).length
  return [
    { label: '运行机组', value: countOf('运行') },
    { label: '备用机组', value: countOf('备用') },
    { label: '故障机组', value: countOf('故障') },
    { label: '已停机机组', value: countOf('已停机') },
  ]
})

function isLocked(row: Row) {
  return row.status === '已停机'
}

function availableActions(row: Row) {
  return ACTIONS_BY_STATUS[String(row.status)] ?? []
}

function displayValue(row: Row, column: string) {
  // 机组状态只认后端同步后的结论，列表与详情、弹窗口径一致
  if (column === '机组状态') return row.status ?? '—'
  const value = row[column]
  return value === null || value === undefined || value === '' ? '—' : value
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  messageOk.value = false
  message.value = '水泵机组登记入口尚未接入审批流'
}

function openDetail(row: Row) {
  void router.push({ name: 'pump-detail', params: { id: String(row.id) } })
}

function openRecords(row: Row) {
  // 直接把当前机组的 id 传进去；弹窗内部按 id 重新拉取，表单随机组重建
  recordEntryId.value = Number(row.id)
}

async function runAction(action: string, row: Row) {
  message.value = ''
  messageOk.value = false
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      message.value = payload?.message ?? '泵站运行动作未生效，请稍后重试'
      return
    }
    messageOk.value = true
    message.value = payload.message
    await reload()
  } catch (error) {
    messageOk.value = false
    message.value = error instanceof Error ? error.message : '泵站运行操作失败'
  }
}

async function reload() {
  message.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('水泵机组列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    messageOk.value = false
    message.value = error instanceof Error ? error.message : '泵站运行列表读取失败'
  }
}

onMounted(reload)
</script>
