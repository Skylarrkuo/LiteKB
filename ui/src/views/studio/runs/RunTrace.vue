<template>
  <article class="trace">
    <div class="identity">
      <span class="identity-mark" aria-hidden="true"
        ><el-icon><Connection /></el-icon
      ></span>
      <div>
        <span class="caption">Run ID</span><code>{{ run.id }}</code>
      </div>
      <span role="status"><RunStatus :status="run.status" /></span>
    </div>

    <div v-if="run.error" class="trace-error">
      <el-icon aria-hidden="true"><WarningFilled /></el-icon>
      <span>{{
        te('runTrace.errors.' + run.error) ? t('runTrace.errors.' + run.error) : run.error
      }}</span>
      <code v-if="te('runTrace.errors.' + run.error)">{{ run.error }}</code>
    </div>

    <dl class="facts">
      <div>
        <dt>{{ t('studio.subject') }}</dt>
        <dd>{{ run.subject }}</dd>
      </div>
      <div>
        <dt>{{ t('studio.started') }}</dt>
        <dd>{{ date(run.created_at) }}</dd>
      </div>
      <div>
        <dt>{{ t('runTrace.used') }}</dt>
        <dd>{{ duration(run.budget?.used_runtime_seconds ?? 0, locale) }}</dd>
      </div>
      <div v-if="run.budget?.max_runtime_seconds != null">
        <dt>{{ t('runTrace.budget') }}</dt>
        <dd>{{ duration(run.budget.max_runtime_seconds, locale) }}</dd>
      </div>
    </dl>
    <details class="reference">
      <summary>{{ t('runTrace.info') }}</summary>
      <dl>
        <div v-for="[key, value] in identifiers" :key="key">
          <dt>{{ key }}</dt>
          <dd>
            <code>{{ value }}</code>
          </dd>
        </div>
        <div>
          <dt>{{ t('runTrace.update') }}</dt>
          <dd>{{ date(run.updated_at) }}</dd>
        </div>
      </dl>
    </details>

    <el-tabs v-model="tab" class="trace-tabs">
      <el-tab-pane name="steps" :label="t('studio.steps') + ' (' + run.steps.length + ')'">
        <p v-if="!run.steps.length" class="empty">{{ t('runTrace.noSteps') }}</p>
        <ol v-else class="step-list">
          <li
            v-for="step in steps"
            :key="JSON.stringify([step.node_id, step.execution_path, step.attempt])"
          >
            <span class="rail-mark" :data-status="step.status" aria-hidden="true"></span>
            <details>
              <summary>
                <span class="node-heading"
                  ><strong>{{ nodeLabel(step.node_type) }}</strong
                  ><code>{{ step.node_id }}</code></span
                >
                <span class="step-tags"
                  ><span v-if="iterations(step).length" class="iteration">{{
                    t('runTrace.loop', { n: iterations(step).join(' / ') })
                  }}</span
                  ><span v-if="step.attempt > 1">{{
                    t('runTrace.attempt', { n: step.attempt })
                  }}</span></span
                >
                <span class="step-meta"
                  ><RunStatus :status="step.status" /><span>{{
                    duration(step.elapsed_seconds, locale)
                  }}</span></span
                >
              </summary>
              <div class="step-info">
                <dl>
                  <div>
                    <dt>{{ t('runTrace.nodeType') }}</dt>
                    <dd>
                      <code>{{ step.node_type }}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>{{ t('runTrace.path') }}</dt>
                    <dd>
                      <code>{{ step.execution_path.join(' / ') }}</code>
                    </dd>
                  </div>
                  <div>
                    <dt>{{ t('studio.attempt') }}</dt>
                    <dd>{{ step.attempt }}</dd>
                  </div>
                </dl>
                <details v-if="Object.keys(step.output_ref || {}).length">
                  <summary>{{ t('studio.outputRef') }}</summary>
                  <pre>{{ JSON.stringify(step.output_ref, null, 2) }}</pre>
                </details>
              </div>
            </details>
          </li>
        </ol>
      </el-tab-pane>
      <el-tab-pane name="events" lazy :label="t('studio.events') + ' (' + run.events.length + ')'">
        <p v-if="run.events[0]?.sequence > 1" class="window-note">
          {{
            t('runTrace.window', {
              first: run.events[0].sequence,
              last: run.events[run.events.length - 1].sequence,
            })
          }}
        </p>
        <p v-if="!run.events.length" class="empty">{{ t('runTrace.noEvents') }}</p>
        <ol v-else class="event-list">
          <li v-for="event in run.events" :key="event.sequence">
            <details>
              <summary>
                <code class="seq">#{{ event.sequence }}</code>
                <span class="event-name"
                  ><strong>{{ eventLabel(event.kind) }}</strong
                  ><code>{{ event.kind }}</code></span
                >
                <time :datetime="event.created_at" :title="date(event.created_at)">{{
                  time(event.created_at)
                }}</time>
              </summary>
              <pre>{{ JSON.stringify(event.data, null, 2) }}</pre>
            </details>
          </li>
        </ol>
      </el-tab-pane>
      <el-tab-pane name="result" lazy :label="t('studio.output')">
        <p v-if="!Object.keys(run.result || {}).length" class="empty">
          {{ t('runTrace.noResult') }}
        </p>
        <template v-else>
          <p v-if="run.result.answer" class="answer">{{ run.result.answer }}</p>
          <dl v-if="run.result.usage" class="facts usage">
            <div>
              <dt>{{ t('runTrace.inputTokens') }}</dt>
              <dd>{{ run.result.usage.input_tokens?.toLocaleString(locale) }}</dd>
            </div>
            <div>
              <dt>{{ t('runTrace.outputTokens') }}</dt>
              <dd>{{ run.result.usage.output_tokens?.toLocaleString(locale) }}</dd>
            </div>
          </dl>
          <details v-if="run.result.sources?.length" class="reference">
            <summary>{{ t('runTrace.sources') }} ({{ run.result.sources.length }})</summary>
            <pre>{{ JSON.stringify(run.result.sources, null, 2) }}</pre>
          </details>
          <details class="reference">
            <summary>{{ t('runTrace.raw') }}</summary>
            <pre>{{ JSON.stringify(run.result, null, 2) }}</pre>
          </details>
        </template>
      </el-tab-pane>
    </el-tabs>
  </article>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Connection, WarningFilled } from '@element-plus/icons-vue'
import RunStatus from './RunStatus.vue'
import { duration, iterations, orderedSteps, type RunDetail } from './trace'
const props = defineProps<{ run: RunDetail }>()
const { locale, t, te } = useI18n({ useScope: 'global' })
const steps = computed(() => orderedSteps(props.run.steps, props.run.events))
const tab = ref(!props.run.steps.length && props.run.events.length ? 'events' : 'steps')
const date = (v: string) => new Date(v).toLocaleString(locale.value)
const time = (v: string) => new Date(v).toLocaleTimeString(locale.value)
const identifiers = computed(() => [
  [t('runTrace.agent'), props.run.agent_id],
  [t('runTrace.version'), props.run.version_id],
  [t('studio.client'), props.run.client_id],
  [t('studio.session'), props.run.session_id],
  ...(props.run.chat_record_id ? [[t('runTrace.chat'), props.run.chat_record_id]] : []),
])
function nodeLabel(value: string) {
  const key =
    'workflow.nodes.' +
    value.replace(/-([a-z])/g, (_, char: string) => char.toUpperCase()) +
    '.label'
  return te(key) ? t(key) : value
}
const eventKeys: Record<string, string> = {
  'step.started': 'start',
  'step.finished': 'finish',
  'answer.delta': 'delta',
  'tool.dispatched': 'tool',
  'run.cancel_requested': 'cancelRequest',
}
function eventLabel(kind: string) {
  const key =
    kind.startsWith('run.') && kind !== 'run.cancel_requested'
      ? 'runTrace.states.' + kind.slice(4)
      : 'runTrace.' + eventKeys[kind]
  return te(key) ? t(key) : kind
}
</script>
<style scoped>
.trace {
  color: var(--el-text-color-primary);
}
.identity {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--app-layout-bg-color);
  border-radius: var(--app-border-radius-large);
}
.identity-mark {
  display: grid;
  place-items: center;
  flex: none;
  width: 38px;
  height: 38px;
  font-size: 20px;
  color: var(--studio-ink);
  background: var(--studio-selection);
  border-radius: 12px;
}
.identity > div {
  min-width: 0;
  flex: 1;
}
.caption,
dt,
time,
.step-meta > span:last-child,
.step-tags,
.event-name code,
.node-heading code {
  color: var(--app-text-color-secondary);
  font-size: 12px;
}
.caption,
.identity code,
.event-name code,
.node-heading code {
  display: block;
}
code,
pre,
.seq {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 12px;
}
code,
dd {
  overflow-wrap: anywhere;
}
.facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin: 18px 0;
}
dt {
  margin-bottom: 3px;
}
dd {
  margin: 0;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}
.reference {
  margin: 8px 0;
  border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-base);
  padding: 9px 12px;
}
summary {
  cursor: pointer;
  line-height: 1.5;
}
summary:focus-visible {
  outline: 2px solid var(--studio-ink);
  outline-offset: 2px;
  border-radius: 4px;
}
.reference dl,
.step-info dl {
  display: grid;
  gap: 8px 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin: 12px 0 4px;
}
.trace-tabs {
  margin-top: 20px;
}
.empty,
.window-note {
  padding: 12px 0;
  color: var(--app-text-color-secondary);
}
.step-list,
.event-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.step-list > li {
  position: relative;
  padding: 0 0 8px 23px;
}
.step-list > li:not(:last-child)::before {
  content: '';
  position: absolute;
  top: 23px;
  bottom: -18px;
  left: 5px;
  border-left: 1px solid var(--studio-hairline);
}
.rail-mark {
  position: absolute;
  top: 20px;
  left: 1px;
  width: 9px;
  height: 9px;
  background: var(--el-text-color-secondary);
  border: 2px solid var(--app-view-bg-color);
  box-sizing: content-box;
  border-radius: 100%;
  transform: translateX(-2px);
}
.rail-mark[data-status='succeeded'] {
  background: #398259;
}
.rail-mark[data-status='failed'] {
  background: #b24743;
}
.rail-mark[data-status='waiting_input'] {
  background: #a97122;
}
.step-list > li > details {
  border: 1px solid var(--studio-hairline);
  border-radius: var(--app-border-radius-base);
}
.step-list > li > details > summary,
.event-list summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  list-style: none;
}
.step-list > li > details > summary::after,
.event-list summary::after {
  content: '';
  width: 6px;
  height: 6px;
  border: solid var(--app-text-color-secondary);
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(-45deg);
  margin-right: 3px;
  flex: none;
}
.step-list > li > details[open] > summary::after,
.event-list details[open] summary::after {
  transform: rotate(45deg);
}
.node-heading,
.event-name {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.step-tags,
.step-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.step-meta > span:last-child,
time {
  font-variant-numeric: tabular-nums;
}
.iteration {
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--app-layout-bg-color);
}
.step-info {
  margin: 0 12px 12px;
  border-top: 1px solid var(--studio-hairline);
}
.step-info details {
  margin-top: 8px;
}
pre {
  margin-top: 8px;
  padding: 10px;
  background: var(--app-layout-bg-color);
  border-radius: var(--app-border-radius-small);
  white-space: pre-wrap;
  word-break: normal;
  overflow-wrap: anywhere;
  line-height: 1.5;
  max-height: 340px;
  overflow: auto;
}
.event-list > li {
  border-bottom: 1px solid var(--studio-hairline);
}
.event-list pre {
  margin: 0 8px 8px;
}
.seq {
  width: 5ch;
  flex: none;
  color: var(--studio-ink);
}
.trace-error {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding: 10px 12px;
  background: #fbe9e7;
  color: #95342f;
  border-radius: var(--app-border-radius-small);
  overflow-wrap: anywhere;
}
.answer {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  line-height: 1.65;
}
.usage {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
@media (max-width: 620px) {
  .facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .reference dl,
  .step-info dl {
    grid-template-columns: minmax(0, 1fr);
  }
  .identity {
    flex-wrap: wrap;
    gap: 8px;
    padding: 12px;
  }
  .identity-mark {
    display: none;
  }
  .step-list > li > details > summary {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
  }
  .node-heading {
    grid-column: 1;
  }
  .step-tags:not(:empty),
  .step-meta {
    grid-column: 1;
  }
  .step-tags:empty {
    display: none;
  }
  .step-list > li > details > summary::after {
    grid-column: 2;
    grid-row: 1;
  }
  .event-list summary {
    gap: 6px;
    padding: 9px 2px;
  }
}
</style>
