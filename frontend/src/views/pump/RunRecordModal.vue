<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <section class="modal-panel" role="dialog" aria-modal="true">
      <header class="modal-head">
        <h3>运行记录 · {{ entry?.机组编号 ?? '加载中' }}</h3>
        <button class="modal-close" type="button" @click="$emit('close')">×</button>
      </header>
      <p v-if="entry" class="modal-sub">
        水泵型号：{{ entry.水泵型号 }} ｜ 所属厂站：{{ entry.所属厂站 }} ｜
        当前结论：<strong>{{ entry.机组状态 }}</strong>
      </p>
      <p v-if="locked" class="lock-banner">
        该机组已停机，运行数据与状态均已锁定：可以查看历史记录，但不能再提交或修改。
      </p>

      <form class="modal-form" @submit.prevent="submit">
        <label>
          <span>运行电流</span>
          <input v-model="form.运行电流" type="text" :disabled="locked" placeholder="如 186A" />
        </label>
        <label>
          <span>累计运行时间（必填）</span>
          <input v-model="form.累计运行时间" type="text" :disabled="locked" placeholder="如 1250h" />
        </label>
        <label>
          <span>轴承温度</span>
          <input v-model="form.轴承温度" type="text" :disabled="locked" placeholder="如 46.5℃" />
        </label>
        <div class="modal-foot" style="grid-column: 1 / -1">
          <button class="btn" type="button" @click="$emit('close')">关闭</button>
          <button class="btn primary" type="submit" :disabled="locked || submitting">提交运行数据</button>
        </div>
      </form>

      <p v-if="message" :class="messageOk ? 'success-text' : 'error-text'">{{ message }}</p>

      <table class="data-table">
        <thead>
          <tr>
            <th>记录时间</th>
            <th>运行电流</th>
            <th>累计运行时间</th>
            <th>轴承温度</th>
            <th>提交时结论</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(record, index) in records" :key="index">
            <td>{{ record.记录时间 }}</td>
            <td>{{ record.运行电流 || '—' }}</td>
            <td>{{ record.累计运行时间 || '—' }}</td>
            <td>{{ record.轴承温度 || '—' }}</td>
            <td>{{ record.机组状态 }}</td>
          </tr>
          <tr v-if="!records.length">
            <td colspan="5" class="empty-state">该机组暂无运行记录</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

interface RunRecord {
  记录时间: string
  机组编号: string
  水泵型号: string
  运行电流: string
  累计运行时间: string
  轴承温度: string
  机组状态: string
}

interface PumpEntry extends Record<string, string | number | RunRecord[] | null> {
  id: number
  机组编号: string
  所属厂站: string
  水泵型号: string
  额定流量: string
  运行电流: string
  累计运行时间: string
  轴承温度: string
  机组状态: string
  status: string
  run_records: RunRecord[]
}

const props = defineProps<{ entryId: number }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const ENDPOINT = `/api/pump/${props.entryId}`

const entry = ref<PumpEntry | null>(null)
const submitting = ref(false)
const message = ref('')
const messageOk = ref(false)

// 表单在每次打开弹窗时新建，仅用当前机组自己的数据初始化，不与上一条机组共享
const form = reactive({ 运行电流: '', 累计运行时间: '', 轴承温度: '' })

const locked = computed(() => entry.value?.status === '已停机')
const records = computed<RunRecord[]>(() => entry.value?.run_records ?? [])

async function loadEntry() {
  message.value = ''
  messageOk.value = false
  const response = await request(ENDPOINT)
  if (!response.ok) {
    message.value = '机组明细读取失败'
    return
  }
  const data = (await response.json()) as PumpEntry
  entry.value = data
  // 三项分别从本条机组取值，互不覆盖
  form.运行电流 = data.运行电流 ?? ''
  form.累计运行时间 = data.累计运行时间 ?? ''
  form.轴承温度 = data.轴承温度 ?? ''
}

async function submit() {
  message.value = ''
  messageOk.value = false
  if (!form.累计运行时间.trim()) {
    message.value = '累计运行时间为空，不允许提交：请先填写该机组的累计运行时间'
    return
  }
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/run-records`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...form } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      message.value = payload?.message ?? '运行数据提交失败，请稍后重试'
      return
    }
    messageOk.value = true
    message.value = payload.message
    await loadEntry()
    emit('saved')
  } catch (error) {
    message.value = error instanceof Error ? error.message : '运行数据提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(loadEntry)
</script>
