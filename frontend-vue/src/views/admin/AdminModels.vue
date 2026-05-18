<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUIStore } from '@/stores'
import { adminApi } from '@/api/admin'
import type { ModelEntry, AuditEntry, ModelMetricsItem } from '@/api/admin'

const { t } = useI18n()
const uiStore = useUIStore()

const entries = ref<ModelEntry[]>([])
const loading = ref(false)
const selected = ref<ModelEntry | null>(null)
const editModel = ref('')
const editVersion = ref('')
const editReason = ref('')
const auditRows = ref<AuditEntry[]>([])
const metrics = ref<ModelMetricsItem[]>([])
const metricsWindow = ref(7)
const saving = ref(false)
const filterText = ref('')

// Human-readable label + family grouping for each service_key. Keeps the
// long cryptic dict readable for non-engineer admins (the original ask
// behind /admin/models). Unknown keys fall back to the raw string + "Other".
const SERVICE_META: Record<string, { family: string; label: string }> = {
  kling_video:              { family: 'Kling',         label: 'Kling Video (T2V/I2V model)' },
  kling_video_effects:      { family: 'Kling',         label: 'Kling Video Effects' },
  kling_try_on:             { family: 'Kling',         label: 'Kling Virtual Try-On' },
  kling_avatar:             { family: 'Kling',         label: 'Kling Avatar (talking head)' },
  kling_lip_sync:           { family: 'Kling',         label: 'Kling Lip-Sync' },
  kling_video_version:      { family: 'Kling',         label: 'Kling Video default version' },
  kling_flagship_version:   { family: 'Kling',         label: 'Kling Video flagship (pro) version' },
  trellis_v1:               { family: 'Trellis (3D)',  label: 'Trellis v1 (cheap 3D)' },
  trellis_v2:               { family: 'Trellis (3D)',  label: 'Trellis v2 (HQ 3D)' },
  flux_t2i:                 { family: 'Flux',          label: 'Flux text-to-image' },
  flux_i2i:                 { family: 'Flux',          label: 'Flux image-to-image' },
  flux_kontext:             { family: 'Flux',          label: 'Flux Kontext (editing)' },
  wan_video:                { family: 'Wan',           label: 'Wan video model' },
  wan_i2v_task:             { family: 'Wan',           label: 'Wan image-to-video task_type' },
  wan_t2v_task:             { family: 'Wan',           label: 'Wan text-to-video task_type' },
  image_toolkit:            { family: 'Image toolkit', label: 'Image toolkit (bg-remove / upscale)' },
  tts_f5:                   { family: 'TTS',           label: 'F5-TTS (voice cloning)' },
  tts_openai:               { family: 'TTS',           label: 'OpenAI-compat TTS (tts-1)' },
  midjourney:               { family: 'Midjourney',    label: 'Midjourney (alias)' },
  luma_video:               { family: 'Luma',          label: 'Luma Dream Machine' },
  luma_ray_version:         { family: 'Luma',          label: 'Luma Ray version' },
}

function metaFor(key: string) {
  return SERVICE_META[key] ?? { family: 'Other', label: key }
}

const filteredEntries = computed(() => {
  const q = filterText.value.trim().toLowerCase()
  if (!q) return entries.value
  return entries.value.filter(e => {
    const m = metaFor(e.service_key)
    return (
      e.service_key.toLowerCase().includes(q)
      || m.label.toLowerCase().includes(q)
      || m.family.toLowerCase().includes(q)
      || (e.effective.model || '').toLowerCase().includes(q)
    )
  })
})

const groupedEntries = computed(() => {
  const groups: Record<string, ModelEntry[]> = {}
  for (const entry of filteredEntries.value) {
    const family = metaFor(entry.service_key).family
    if (!groups[family]) groups[family] = []
    groups[family].push(entry)
  }
  // Preserve a stable family order; "Other" sinks to the bottom
  const order = ['Kling', 'Flux', 'Wan', 'Midjourney', 'Luma', 'Trellis (3D)', 'Image toolkit', 'TTS', 'Other']
  return order
    .filter(f => groups[f])
    .map(f => ({ family: f, items: groups[f] }))
})

async function loadAll() {
  loading.value = true
  try {
    const res = await adminApi.listModels()
    entries.value = res.entries
  } catch (err: any) {
    uiStore.showError(err?.response?.data?.detail || t('adminModels.errors.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function selectEntry(entry: ModelEntry) {
  selected.value = entry
  editModel.value = entry.effective.model
  editVersion.value = entry.effective.version || ''
  editReason.value = ''
  await Promise.all([loadAudit(entry.service_key), loadMetrics(entry.service_key)])
}

async function loadAudit(serviceKey: string) {
  try {
    const res = await adminApi.getModelAudit(serviceKey, 50)
    auditRows.value = res.entries
  } catch {
    auditRows.value = []
  }
}

async function loadMetrics(serviceKey: string) {
  try {
    const res = await adminApi.getModelMetrics(serviceKey, metricsWindow.value)
    metrics.value = res.metrics_by_model
  } catch {
    metrics.value = []
  }
}

async function save() {
  if (!selected.value) return
  if (!editModel.value.trim()) {
    uiStore.showWarning(t('adminModels.warnings.modelRequired'))
    return
  }
  saving.value = true
  try {
    const refreshed = await adminApi.updateModel(selected.value.service_key, {
      model: editModel.value.trim(),
      version: editVersion.value.trim() || null,
      reason: editReason.value.trim() || null,
    })
    // Patch in place so the list updates without a full reload
    const idx = entries.value.findIndex(e => e.service_key === refreshed.service_key)
    if (idx >= 0) entries.value[idx] = refreshed
    selected.value = refreshed
    editReason.value = ''
    await loadAudit(refreshed.service_key)
    uiStore.showSuccess(t('adminModels.toasts.saved'))
  } catch (err: any) {
    uiStore.showError(err?.response?.data?.detail || t('adminModels.errors.saveFailed'))
  } finally {
    saving.value = false
  }
}

const sourceBadgeClass = (source: string) => {
  if (source === 'db') return 'bg-blue-500/20 text-blue-300'
  if (source === 'env') return 'bg-yellow-500/20 text-yellow-300'
  if (source === 'default') return 'bg-gray-500/20 text-gray-300'
  return 'bg-red-500/20 text-red-300'
}

const isOverridden = (e: ModelEntry) =>
  e.override !== null && (
    e.override.model !== e.default.model ||
    (e.override.version || null) !== (e.default.version || null)
  )

const overriddenCount = computed(() => entries.value.filter(isOverridden).length)

onMounted(loadAll)
</script>

<template>
  <div class="min-h-screen pt-6 pb-20" style="background: #09090b;">
    <div class="max-w-7xl mx-auto px-4">
      <div class="mb-6">
        <h1 class="text-2xl font-bold" style="color: #f5f5fa;">{{ t('adminModels.title') }}</h1>
        <p class="text-sm mt-1" style="color: #9494b0;">{{ t('adminModels.subtitle') }}</p>
        <div class="text-xs mt-3 p-3 rounded-lg" style="background: rgba(255,193,7,0.08); color: #ffc107; border: 1px solid rgba(255,193,7,0.2);">
          ⚠️ {{ t('adminModels.restartWarning') }}
        </div>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- LEFT: service_key list, grouped by family with filter -->
        <div class="lg:col-span-2 rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-sm font-semibold" style="color: #e8e8f0;">{{ t('adminModels.listTitle') }}</h2>
            <span class="text-xs" style="color: #9494b0;">
              {{ t('adminModels.overriddenSummary', { n: overriddenCount, total: entries.length }) }}
            </span>
          </div>

          <input
            v-model="filterText"
            type="text"
            :placeholder="t('adminModels.filterPlaceholder')"
            class="w-full mb-3 px-3 py-2 rounded text-sm"
            style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
          />

          <div v-if="loading" class="py-8 text-center text-sm" style="color: #6b6b8a;">{{ t('common.loading') }}</div>

          <div v-else-if="filteredEntries.length === 0" class="py-8 text-center text-sm" style="color: #6b6b8a;">
            {{ t('adminModels.noMatches') }}
          </div>

          <div v-else class="space-y-4">
            <div v-for="group in groupedEntries" :key="group.family">
              <div class="text-xs font-semibold uppercase tracking-wider mb-2" style="color: #6b6b8a;">
                {{ group.family }}
                <span class="ml-1" style="color: #4b4b62;">({{ group.items.length }})</span>
              </div>
              <div class="space-y-1">
                <div
                  v-for="entry in group.items"
                  :key="entry.service_key"
                  @click="selectEntry(entry)"
                  class="cursor-pointer rounded-lg p-3 transition-all"
                  :style="selected?.service_key === entry.service_key
                    ? 'background: rgba(22,119,255,0.12); border: 1px solid rgba(22,119,255,0.4);'
                    : 'background: #0d0d15; border: 1px solid rgba(255,255,255,0.06);'"
                >
                  <div class="flex items-center justify-between">
                    <div class="text-sm font-medium" style="color: #e8e8f0;">
                      {{ metaFor(entry.service_key).label }}
                    </div>
                    <span class="text-xs px-2 py-0.5 rounded" :class="sourceBadgeClass(entry.effective.source)">
                      {{ entry.effective.source }}
                    </span>
                  </div>
                  <div class="mt-1 text-xs flex items-center gap-2" style="color: #9494b0;">
                    <span class="font-mono">{{ entry.service_key }}</span>
                    <span class="opacity-50">·</span>
                    <span class="font-mono">{{ entry.effective.model }}</span>
                    <span v-if="entry.effective.version" class="font-mono">v{{ entry.effective.version }}</span>
                    <span v-if="isOverridden(entry)" class="text-blue-400">• {{ t('adminModels.overridden') }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- RIGHT: edit panel -->
        <div class="rounded-xl p-4" style="background: #141420; border: 1px solid rgba(255,255,255,0.06);">
          <h2 class="text-sm font-semibold mb-3" style="color: #e8e8f0;">{{ t('adminModels.editTitle') }}</h2>

          <div v-if="!selected" class="py-8 text-center text-sm" style="color: #6b6b8a;">
            {{ t('adminModels.pickHint') }}
          </div>

          <div v-else class="space-y-3">
            <div>
              <label class="block text-xs mb-1" style="color: #9494b0;">{{ t('adminModels.serviceKey') }}</label>
              <div class="font-mono text-sm px-3 py-2 rounded" style="background: #0d0d15; color: #e8e8f0;">
                {{ selected.service_key }}
              </div>
            </div>

            <div>
              <label class="block text-xs mb-1" style="color: #9494b0;">{{ t('adminModels.modelLabel') }}</label>
              <input
                v-model="editModel"
                class="w-full px-3 py-2 rounded text-sm font-mono"
                style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
              />
              <div class="text-xs mt-1" style="color: #6b6b8a;">
                {{ t('adminModels.defaultHint', { model: selected.default.model }) }}
              </div>
            </div>

            <div>
              <label class="block text-xs mb-1" style="color: #9494b0;">{{ t('adminModels.versionLabel') }}</label>
              <input
                v-model="editVersion"
                :placeholder="t('adminModels.versionPlaceholder')"
                class="w-full px-3 py-2 rounded text-sm font-mono"
                style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
              />
            </div>

            <div>
              <label class="block text-xs mb-1" style="color: #9494b0;">{{ t('adminModels.reasonLabel') }}</label>
              <textarea
                v-model="editReason"
                rows="2"
                :placeholder="t('adminModels.reasonPlaceholder')"
                class="w-full px-3 py-2 rounded text-sm"
                style="background: #0d0d15; color: #e8e8f0; border: 1px solid rgba(255,255,255,0.1);"
              />
            </div>

            <button
              @click="save"
              :disabled="saving"
              class="w-full py-2 rounded-lg text-sm font-semibold text-white transition-all disabled:opacity-50"
              style="background: #1677ff;"
            >
              {{ saving ? t('adminModels.saving') : t('adminModels.save') }}
            </button>

            <!-- Metrics tile -->
            <div class="mt-4 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
              <h3 class="text-sm font-semibold mb-2" style="color: #e8e8f0;">
                {{ t('adminModels.metricsTitle', { days: metricsWindow }) }}
              </h3>
              <div v-if="metrics.length === 0" class="text-xs py-3" style="color: #6b6b8a;">
                {{ t('adminModels.metricsEmpty') }}
              </div>
              <div v-else class="space-y-2">
                <div v-for="m in metrics" :key="m.model_used" class="text-xs p-2 rounded" style="background: #0d0d15;">
                  <div class="font-mono" style="color: #e8e8f0;">{{ m.model_used }}</div>
                  <div class="grid grid-cols-3 gap-2 mt-1" style="color: #9494b0;">
                    <div>
                      <div>{{ t('adminModels.metricSuccessRate') }}</div>
                      <div class="font-semibold" style="color: #4ade80;">{{ (m.success_rate * 100).toFixed(1) }}%</div>
                    </div>
                    <div>
                      <div>{{ t('adminModels.metricAvgLatency') }}</div>
                      <div class="font-semibold" style="color: #e8e8f0;">{{ m.avg_duration_ms ? `${m.avg_duration_ms}ms` : '—' }}</div>
                    </div>
                    <div>
                      <div>{{ t('adminModels.metricCost') }}</div>
                      <div class="font-semibold" style="color: #e8e8f0;">${{ m.total_cost_usd.toFixed(2) }}</div>
                    </div>
                  </div>
                  <div class="mt-1" style="color: #6b6b8a;">
                    {{ t('adminModels.metricCalls', { n: m.total_calls }) }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Audit log -->
            <div class="mt-4 pt-4" style="border-top: 1px solid rgba(255,255,255,0.06);">
              <h3 class="text-sm font-semibold mb-2" style="color: #e8e8f0;">{{ t('adminModels.auditTitle') }}</h3>
              <div v-if="auditRows.length === 0" class="text-xs py-3" style="color: #6b6b8a;">
                {{ t('adminModels.auditEmpty') }}
              </div>
              <div v-else class="space-y-2 max-h-96 overflow-y-auto">
                <div v-for="row in auditRows" :key="row.id" class="text-xs p-2 rounded" style="background: #0d0d15;">
                  <div style="color: #9494b0;">{{ new Date(row.changed_at).toLocaleString() }}</div>
                  <div class="font-mono mt-1" style="color: #e8e8f0;">
                    <span style="color: #6b6b8a;">{{ row.before_model || '—' }}{{ row.before_version ? ` v${row.before_version}` : '' }}</span>
                    →
                    <span>{{ row.after_model }}{{ row.after_version ? ` v${row.after_version}` : '' }}</span>
                  </div>
                  <div v-if="row.reason" class="mt-1 italic" style="color: #9494b0;">"{{ row.reason }}"</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
