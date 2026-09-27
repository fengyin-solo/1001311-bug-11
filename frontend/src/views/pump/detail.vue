<template>
  <section class="page" data-module="pump-detail">
    <header class="detail-head">
      <div>
        <h2>机组详情 · {{ entry?.机组编号 ?? '加载中' }}</h2>
        <p class="page-desc">详情、列表与运行记录弹窗共用同一状态来源，结论保持一致。</p>
      </div>
      <button class="btn" type="button" @click="goBack">返回泵站列表</button>
    </header>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>

    <template v-if="entry">
      <div class="detail-grid">
        <article v-for="field in infoFields" :key="field" class="detail-card">
          <span>{{ field }}</span>
          <strong>{{ field === '机组状态' ? entry.status : (entry[field] || '—') }}</strong>
        </article>
      </div>

      <div class="page-actions" style="margin: 14px 0">
        <template v-if="!locked">
          <button class="btn primary" type="button" @click="showRecords = true">提交/查看运行数据</button>
          <button
            v-for="action in availableActions"
            :key="action"
            class="btn"
            type="button"
            @click="runAction(action)"
          >
            {{ action }}
          </button>
        </template>
        <button v-else class="btn" type="button" @click="showRecords = true">查看运行记录（已停机，只读）</button>
      </div>
      <p v-if="locked" class="lock-banner">该机组已停机，可查询档案与历史运行记录，但状态和运行数据均不可修改。</p>
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
          <tr v-for="(record, index) in entry.run_records" :key="index">
            <td>{{ record.记录时间 }}</td>
            <td>{{ record.运行电流 || '—' }}</td>
            <td>{{ record.累计运行时间 || '—' }}</td>
            <td>{{ record.轴承温度 || '—' }}</td>
            <td>{{ record.机组状态 }}</td>
          </tr>
          <tr v-if="!entry.run_records.length">
            <td colspan="5" class="empty-state">该机组暂无运行记录</td>
          </tr>
        </tbody>
      </table>
    </template>

    <RunRecordModal
      v-if="showRecords && entry"
      :entry-id="entry.id"
      @close="showRecords = false"
      @saved="refresh"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import RunRecordModal from './RunRecordModal.vue'

interface RunRecord {
  记录时间: string
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

const ACTIONS_BY_STATUS: Record<string, string[]> = {
  "运行": ["切换备用", "标记故障", "故障停机"],
  "备用": ["启用备用", "故障停机"],
  "故障": ["故障停机", "启用备用"],
}
const infoFields = ["机组编号", "所属厂站", "水泵型号", "额定流量", "运行电流", "累计运行时间", "轴承温度", "机组状态"]

const route = useRoute()
const router = useRouter()
const entry = ref<PumpEntry | null>(null)
const loadError = ref('')
const showRecords = ref(false)
const message = ref('')
const messageOk = ref(false)

const entryId = computed(() => Number(route.params.id))
const locked = computed(() => entry.value?.status === '已停机')
const availableActions = computed(() => (entry.value ? ACTIONS_BY_STATUS[String(entry.value.status)] ?? [] : []))

function goBack() {
  // 返回列表时列表会重新拉取，详情本地表单随之销毁，不会把上一条型号带回列表
  void router.push({ name: 'pump' })
}

async function refresh() {
  loadError.value = ''
  try {
    const response = await request(`/api/pump/${entryId.value}`)
    if (!response.ok) {
      throw new Error('机组明细读取失败')
    }
    entry.value = await response.json()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '机组明细读取失败'
  }
}

async function runAction(action: string) {
  message.value = ''
  messageOk.value = false
  try {
    const response = await request(`/api/pump/${entryId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      message.value = payload?.message ?? '动作未生效，请稍后重试'
      return
    }
    messageOk.value = true
    message.value = payload.message
    await refresh()
  } catch (error) {
    messageOk.value = false
    message.value = error instanceof Error ? error.message : '泵站运行操作失败'
  }
}

onMounted(refresh)
</script>
