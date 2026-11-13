<template>
  <section class="runs-page" aria-labelledby="runs-title">
    <header class="page-heading">
      <div>
        <h1 id="runs-title">{{ t('studio.runs') }}</h1>
        <span v-if="hasLoaded" class="count">{{ t('runTrace.count', { n: total }) }}</span>
      </div>
      <div class="controls">
        <el-switch
          v-model="auto"
          size="small"
          :active-text="t('runTrace.auto')"
          :aria-label="t('runTrace.auto')"
        />
        <el-button :icon="Refresh" :loading="listBusy" @click="loadList()">{{
          t('studio.refresh')
        }}</el-button>
      </div>
    </header>
    <div v-if="listError" class="notice" role="alert">
      {{ t('runTrace.listError') }}
      <el-button link type="primary" @click="loadList()">{{ t('runTrace.retry') }}</el-button>
    </div>
    <div class="run-panel" :aria-busy="listBusy">
      <table v-if="rows.length" aria-labelledby="runs-title">
        <thead>
          <tr>
            <th scope="col">Run ID</th>
            <th scope="col">{{ t('studio.status') }}</th>
            <th scope="col">{{ t('studio.subject') }}</th>
            <th scope="col">{{ t('runTrace.agent') }}</th>
            <th scope="col">{{ t('studio.started') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td class="id-cell">
              <button
                type="button"
                class="run-link"
                :aria-label="t('runTrace.open', { id: row.id })"
                :title="row.id"
                @click="inspect(row.id)"
              >
                <el-icon aria-hidden="true"><Connection /></el-icon
                ><code>{{ shortId(row.id) }}</code>
              </button>
            </td>
            <td class="status-cell"><RunStatus :status="row.status" /></td>
            <td>
              <span class="mobile-label">{{ t('studio.subject') }}</span
              ><span>{{ row.subject }}</span>
            </td>
            <td>
              <span class="mobile-label">{{ t('runTrace.agent') }}</span
              ><code :title="row.agent_id">{{ shortId(row.agent_id) }}</code>
            </td>
            <td>
              <span class="mobile-label">{{ t('studio.started') }}</span
              ><time :datetime="row.created_at">{{ date(row.created_at) }}</time>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else-if="listBusy" class="empty" role="status"><el-skeleton animated :rows="3" /></div>
      <div v-else-if="hasLoaded && !listError" class="empty">
        <el-icon class="empty-icon" aria-hidden="true"><List /></el-icon>
        <h2>{{ t('studio.noRuns') }}</h2>
        <p>{{ t('runTrace.empty') }}</p>
      </div>
    </div>
    <el-pagination
      v-if="total > size"
      layout="prev, pager, next"
      :pager-count="5"
      :total="total"
      :page-size="size"
      :current-page="page"
      @update:current-page="changePage"
    />

    <el-drawer
      v-model="open"
      :title="t('studio.trace')"
      size="min(790px, 100%)"
      append-to-body
      destroy-on-close
      @close="closeTrace"
    >
      <template #header="{ titleId, titleClass }">
        <div class="drawer-heading">
          <h2 :id="titleId" :class="titleClass">{{ t('studio.trace') }}</h2>
          <el-button
            :icon="Refresh"
            :loading="detailBusy"
            :aria-label="t('studio.refresh')"
            :title="t('studio.refresh')"
            circle
            @click="loadDetail()"
          />
        </div>
      </template>
      <div v-if="detailError" class="notice" role="alert">
        {{ t('runTrace.detailError') }}
        <el-button link type="primary" @click="loadDetail()">{{ t('runTrace.retry') }}</el-button>
      </div>
      <RunTrace v-if="detail" :key="detail.id" :run="detail" />
      <el-skeleton v-else-if="detailBusy" animated :rows="6" />
    </el-drawer>
  </section>
</template>
<script setup lang="ts">
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Connection, List, Refresh } from '@element-plus/icons-vue'
import { get } from '@/request'
import RunTrace from './runs/RunTrace.vue'
import RunStatus from './runs/RunStatus.vue'
import { isActiveRun, shortId, type RunDetail, type RunRow } from './runs/trace'

const { t, locale } = useI18n({ useScope: 'global' })
const date = (v: string) => new Date(v).toLocaleString(locale.value)
const page = ref(1),
  total = ref(0),
  size = 25
const rows = ref<RunRow[]>([]),
  detail = ref<RunDetail>()
const auto = ref(true),
  open = ref(false),
  hasLoaded = ref(false)
const listBusy = ref(false),
  listError = ref(false),
  detailBusy = ref(false),
  detailError = ref(false)
let selected = '',
  listRequest = 0,
  detailRequest = 0
let active = false,
  timer: ReturnType<typeof setTimeout> | undefined
let listPending = false,
  detailPending = false

function stopTimer() {
  clearTimeout(timer)
}
function schedule() {
  stopTimer()
  if (!active || !auto.value || document.hidden) return
  if (open.value) {
    if (detail.value && isActiveRun(detail.value.status) && !detailError.value && !detailPending) {
      timer = setTimeout(
        () => loadDetail(true),
        detail.value.status === 'waiting_input' ? 10000 : 3000,
      )
    }
  } else if (!listError.value && !listPending) {
    timer = setTimeout(() => loadList(true), 10000)
  }
}
function changePage(n: number) {
  if (page.value === n) return
  page.value = n
  loadList()
}
async function loadList(background = false) {
  if (background && listPending) return
  listPending = true
  const request = ++listRequest
  const previousPage = page.value
  if (!background) listBusy.value = true
  listError.value = false
  stopTimer()
  try {
    const { data } = await get('/litekb/runs', { page: previousPage, page_size: size })
    if (request !== listRequest || !active) return
    total.value = data.total
    rows.value = data.items
    hasLoaded.value = true
    const lastPage = Math.max(1, Math.ceil(total.value / size))
    if (page.value > lastPage) {
      page.value = lastPage
      await loadList()
    }
  } catch {
    if (request === listRequest) listError.value = true
  } finally {
    if (request === listRequest) {
      listPending = false
      listBusy.value = false
      schedule()
    }
  }
}
async function loadDetail(background = false) {
  if (!open.value || !selected || (background && detailPending)) return
  detailPending = true
  const request = ++detailRequest
  if (!background) detailBusy.value = true
  detailError.value = false
  stopTimer()
  try {
    const { data } = await get('/litekb/runs/' + selected)
    if (request !== detailRequest || !active || !open.value) return
    detail.value = data
    rows.value = rows.value.map((row) =>
      row.id === data.id ? { ...row, status: data.status, updated_at: data.updated_at } : row,
    )
  } catch {
    if (request === detailRequest) detailError.value = true
  } finally {
    if (request === detailRequest) {
      detailPending = false
      detailBusy.value = false
      schedule()
    }
  }
}
function inspect(id: string) {
  selected = id
  detail.value = undefined
  open.value = true
  loadDetail()
}
function closeTrace() {
  ++detailRequest
  selected = ''
  open.value = false
  detailBusy.value = false
  detailPending = false
  schedule()
}
function visible() {
  if (document.hidden) stopTimer()
  else if (auto.value && active) {
    if (!open.value) loadList(true)
    else if (detail.value && isActiveRun(detail.value.status)) loadDetail(true)
  }
}
function activate() {
  if (active) return
  active = true
  document.addEventListener('visibilitychange', visible)
  loadList()
}
function deactivate() {
  active = false
  ++listRequest
  ++detailRequest
  stopTimer()
  document.removeEventListener('visibilitychange', visible)
  open.value = false
  listPending = false
  detailPending = false
  listBusy.value = false
  detailBusy.value = false
}
watch(auto, schedule)
onMounted(activate)
onActivated(activate)
onDeactivated(deactivate)
onBeforeUnmount(deactivate)
</script>
<style scoped>
.runs-page {
  height: 100%;
  box-sizing: border-box;
  overflow: auto;
  padding: clamp(16px, 2.6vw, 38px);
  color: var(--el-text-color-primary);
}
.page-heading,
.page-heading > div,
.drawer-heading,
.controls {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.page-heading,
.drawer-heading {
  justify-content: space-between;
}
.page-heading {
  flex-wrap: wrap;
  margin-bottom: 20px;
}
h1 {
  font-size: clamp(22px, 2.1vw, 29px);
  line-height: 1.25;
  letter-spacing: -0.035em;
  font-weight: 650;
}
.count {
  padding: 3px 9px;
  font-size: 12px;
  background: var(--studio-selection);
  color: var(--studio-ink);
  border-radius: 99px;
}
.run-panel {
  background: var(--app-view-bg-color);
  border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-large);
  overflow: hidden;
  box-shadow: var(--studio-shadow);
}
.run-panel:empty {
  display: none;
}
table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}
th {
  background: var(--app-layout-bg-color);
  color: var(--app-text-color-secondary);
  font-weight: 550;
  font-size: 12px;
}
th,
td {
  padding: 14px 16px;
  line-height: 1.4;
}
td {
  border-top: 1px solid var(--studio-hairline);
  overflow-wrap: anywhere;
}
tbody tr:focus-within,
tbody tr:hover {
  background: color-mix(in srgb, var(--studio-selection) 33%, var(--app-view-bg-color));
}
.run-link {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  background: none;
  border: 0;
  cursor: pointer;
  color: var(--studio-ink);
  font-weight: 600;
  padding: 5px 2px;
  text-align: left;
}
.run-link:hover code {
  text-decoration: underline;
}
.run-link .el-icon {
  color: var(--studio-ink);
}
code {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}
time {
  font-variant-numeric: tabular-nums;
}
.mobile-label {
  display: none;
}
.empty {
  min-height: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 8px;
  padding: 20px;
}
.empty h2 {
  margin: 4px 0;
  font-size: 17px;
}
.empty p {
  color: var(--app-text-color-secondary);
  max-width: 36em;
}
.empty-icon {
  padding: 12px;
  background: var(--studio-selection);
  color: var(--studio-ink);
  border-radius: 12px;
  font-size: 20px;
}
.el-pagination {
  margin-top: 16px;
}
.notice {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  border: 1px solid var(--el-color-danger-light-7);
  color: var(--el-color-danger-dark-2);
  background: var(--el-color-danger-light-9);
  border-radius: var(--app-border-radius-base);
}
.drawer-heading {
  flex: 1;
}
.drawer-heading h2 {
  color: var(--el-text-color-primary);
  font-size: 20px;
  margin: 0;
}
@media (max-width: 850px) {
  .run-panel table,
  .run-panel tbody {
    display: block;
  }
  thead {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    clip-path: inset(50%);
    overflow: hidden;
  }
  tbody tr {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 6px 12px;
    padding: 12px 14px;
  }
  tbody tr + tr {
    border-top: 1px solid var(--studio-hairline);
  }
  td {
    display: block;
    padding: 0;
    border: 0;
  }
  td:not(.id-cell):not(.status-cell) {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: minmax(75px, auto) minmax(0, 1fr);
    align-items: baseline;
    column-gap: 8px;
    font-size: 13px;
  }
  .mobile-label {
    display: inline;
    color: var(--app-text-color-secondary);
    font-size: 12px;
  }
  .status-cell {
    align-self: center;
  }
}
</style>
