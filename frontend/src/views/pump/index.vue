<template>
  <section class="page" data-module="pump">
    <header class="page-head">
      <div>
        <h2>泵站运行管理</h2>
        <p class="page-desc">机组状态、轴承温度与运行电流按机组编号分开保存；停机后状态同步为已停机，已停机机组只能查看不能改动。</p>
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
        <input v-model="filters.keyword" placeholder="按机组编号检索" />
      </label>
      <label class="filter-item">
        <span>机组状态</span>
        <select v-model="filters.status">
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
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <template v-if="isStopped(row)">
              <span class="link-disabled" title="已停机的机组只能查看，不能改动">提交运行数据</span>
              <span class="link-disabled" title="已停机的机组只能查看，不能改动">停机</span>
            </template>
            <template v-else>
              <button class="link" type="button" @click="openRuntime(row)">提交运行数据</button>
              <button class="link" type="button" @click="stopUnit(row)">停机</button>
            </template>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无泵站运行数据，可先登记水泵机组</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条泵站运行记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detailEntry" class="modal-mask" @click.self="closeDetail">
      <div class="modal-card">
        <header class="modal-head">
          <h3>机组详情 · {{ detailEntry['机组编号'] }}</h3>
          <span class="status-tag">{{ detailEntry['机组状态'] }}</span>
        </header>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detailEntry[column] ?? '—' }}</dd>
          </template>
        </dl>
        <footer class="modal-foot">
          <span v-if="isStopped(detailEntry)" class="muted-text">已停机的机组只能查看，不能改动</span>
          <button class="btn" type="button" @click="closeDetail">返回列表</button>
        </footer>
      </div>
    </div>

    <div v-if="runtimeEntry" class="modal-mask" @click.self="closeRuntime">
      <div class="modal-card">
        <header class="modal-head">
          <h3>提交运行数据 · {{ runtimeEntry['机组编号'] }}</h3>
          <span class="status-tag">{{ runtimeEntry['机组状态'] }}</span>
        </header>
        <p class="muted-text">
          所属厂站：{{ runtimeEntry['所属厂站'] ?? '—' }} · 水泵型号：{{ runtimeEntry['水泵型号'] ?? '—' }}
        </p>
        <form @submit.prevent="submitRuntime">
          <label v-for="field in runtimeFields" :key="field" class="form-item">
            <span>
              {{ field }}
              <em v-if="field === '累计运行时间'" class="required-mark">*</em>
            </span>
            <input
              v-model="runtimeForm[field]"
              :placeholder="`填写 ${runtimeEntry['机组编号']} 的${field}`"
            />
          </label>
          <p v-if="runtimeError" class="error-text">{{ runtimeError }}</p>
          <footer class="modal-foot">
            <button class="btn ghost" type="button" @click="closeRuntime">取消</button>
            <button class="btn primary" type="submit">提交运行数据</button>
          </footer>
        </form>
      </div>
    </div>

    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal-card">
        <header class="modal-head">
          <h3>登记水泵机组</h3>
        </header>
        <form @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field" class="form-item">
            <span>
              {{ field }}
              <em v-if="field !== '额定流量'" class="required-mark">*</em>
            </span>
            <input v-model="createForm[field]" :placeholder="`填写${field}`" />
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
          <footer class="modal-foot">
            <button class="btn ghost" type="button" @click="createVisible = false">取消</button>
            <button class="btn primary" type="submit">登记</button>
          </footer>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/pump'
const columns = ["机组编号", "所属厂站", "水泵型号", "额定流量", "运行电流", "累计运行时间", "轴承温度", "机组状态"]
const statuses = ["运行", "备用", "故障", "已停机"]
const runtimeFields = ["轴承温度", "运行电流", "累计运行时间"]
const createFields = ["机组编号", "所属厂站", "水泵型号", "额定流量"]
const STOPPED = '已停机'

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = reactive({ keyword: '', status: '' })

const stats = computed(() => [
  { label: '运行机组', value: rows.value.filter((row) => row['机组状态'] === '运行').length },
  { label: '备用机组', value: rows.value.filter((row) => row['机组状态'] === '备用').length },
  { label: '已停机机组', value: rows.value.filter((row) => row['机组状态'] === STOPPED).length },
])

const detailEntry = ref<Row | null>(null)
const runtimeEntry = ref<Row | null>(null)
const runtimeForm = reactive<Record<string, string>>({ 轴承温度: '', 运行电流: '', 累计运行时间: '' })
const runtimeError = ref('')
const createVisible = ref(false)
const createForm = reactive<Record<string, string>>({ 机组编号: '', 所属厂站: '', 水泵型号: '', 额定流量: '' })
const createError = ref('')

function isStopped(row: Row) {
  return row['机组状态'] === STOPPED
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function parseResult(response: Response): Promise<{ ok: boolean; message: string; entry?: Row }> {
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，操作未生效`)
  }
  return (await response.json()) as { ok: boolean; message: string; entry?: Row }
}

async function fetchEntry(id: string | number | null): Promise<Row> {
  const response = await request(`${ENDPOINT}/${id}`)
  if (!response.ok) {
    throw new Error('机组数据读取失败，请稍后重试')
  }
  return (await response.json()) as Row
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    // 每次按机组 id 重新取，保证详情与列表是同一个结论，也不带上一条的内容
    detailEntry.value = await fetchEntry(row.id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '机组详情读取失败'
  }
}

function closeDetail() {
  detailEntry.value = null
}

async function openRuntime(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  runtimeError.value = ''
  if (isStopped(row)) {
    errorMessage.value = `机组 ${row['机组编号']} 已停机，只能查看，不能再改动运行数据`
    return
  }
  try {
    const fresh = await fetchEntry(row.id)
    runtimeEntry.value = fresh
    // 表单只装这条机组自己的数据，打开前全部重置，避免被上一条的型号或温度盖掉
    for (const field of runtimeFields) {
      runtimeForm[field] = fresh[field] != null ? String(fresh[field]) : ''
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '运行记录读取失败'
  }
}

function closeRuntime() {
  runtimeEntry.value = null
  runtimeError.value = ''
}

async function submitRuntime() {
  const entry = runtimeEntry.value
  if (!entry) {
    return
  }
  runtimeError.value = ''
  if (!runtimeForm['累计运行时间'].trim()) {
    runtimeError.value = '累计运行时间为空，不允许提交：请填写本次抄表的累计运行时间'
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${entry.id}/runtime`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...runtimeForm } }),
    })
    const result = await parseResult(response)
    if (!result.ok) {
      runtimeError.value = result.message
      return
    }
    closeRuntime()
    noticeMessage.value = result.message
    await reload()
  } catch (error) {
    runtimeError.value = error instanceof Error ? error.message : '运行数据提交失败'
  }
}

async function stopUnit(row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  if (isStopped(row)) {
    return
  }
  if (!window.confirm(`确认停机 ${row['机组编号']}？停机后状态同步为已停机，只能查看不能再改动。`)) {
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/stop`, { method: 'POST' })
    const result = await parseResult(response)
    if (!result.ok) {
      errorMessage.value = result.message
      return
    }
    noticeMessage.value = result.message
    await reload()
    if (detailEntry.value && detailEntry.value.id === row.id) {
      // 详情弹窗若开着同一台机组，跟着服务端结论一起刷新
      detailEntry.value = result.entry ?? (await fetchEntry(row.id))
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '停机操作失败'
  }
}

function openCreate() {
  createError.value = ''
  for (const field of createFields) {
    createForm[field] = ''
  }
  createVisible.value = true
}

async function submitCreate() {
  createError.value = ''
  const missing = createFields.slice(0, 3).filter((field) => !createForm[field].trim())
  if (missing.length) {
    createError.value = `缺少必填字段：${missing.join('、')}`
    return
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const result = await parseResult(response)
    if (!result.ok) {
      createError.value = result.message
      return
    }
    createVisible.value = false
    noticeMessage.value = result.message
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '水泵机组登记失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.keyword.trim()) {
    query.set('keyword', filters.keyword.trim())
  }
  if (filters.status) {
    query.set('status', filters.status)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('水泵机组列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '泵站运行列表读取失败'
  }
}

onMounted(reload)
</script>
