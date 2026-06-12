<script setup lang="ts">
/**
 * AtmosphereControls — shared fine-tune knobs for 立體圖 (Isometric) and
 * 3D 效果圖 (Render3D): lighting tone, color temperature (Kelvin), and an
 * optional material accent. These map 1:1 to the backend's additive
 * atmosphere clauses (interior_design_service.build_atmosphere_clause),
 * which restyle light and surfaces only — geometry is protected by the
 * anti-hallucination invariants, so adjusting these never moves walls or
 * furniture. colorTemperature === 0 means "auto" (no clause sent).
 */
import { computed } from 'vue'
import { useLocalized } from '@/composables'
import type { InteriorLightingTone, InteriorMaterialAccent } from '@/api/interior'

const { L } = useLocalized()

const lightingTone = defineModel<'' | InteriorLightingTone>('lightingTone', { default: '' })
const colorTemperature = defineModel<number>('colorTemperature', { default: 0 })
const materialAccent = defineModel<'' | InteriorMaterialAccent>('materialAccent', { default: '' })

const lightingOptions = computed(() => [
  { id: '' as const,                   label: L('自動', 'Auto', '自動', '자동', 'Auto') },
  { id: 'daylight' as const,           label: L('自然日光', 'Daylight', '自然光', '자연광', 'Luz natural') },
  { id: 'warm_evening' as const,       label: L('黃昏暖光', 'Warm evening', '夕方の暖光', '따뜻한 저녁', 'Tarde cálida') },
  { id: 'golden_hour' as const,        label: L('黃金時刻', 'Golden hour', 'ゴールデンアワー', '골든아워', 'Hora dorada') },
  { id: 'overcast_soft' as const,      label: L('柔和陰天', 'Soft overcast', 'やわらかな曇天', '부드러운 흐림', 'Nublado suave') },
  { id: 'dramatic_spotlight' as const, label: L('戲劇聚光', 'Dramatic spotlight', 'ドラマチック照明', '드라마틱 조명', 'Foco dramático') },
  { id: 'night' as const,              label: L('夜景燈光', 'Night lighting', '夜景照明', '야경 조명', 'Iluminación nocturna') },
])

const materialOptions = computed(() => [
  { id: '' as const,          label: L('— 不指定 —', '— None —', '— 指定なし —', '— 지정 안 함 —', '— Ninguno —') },
  { id: 'wood' as const,      label: L('木質', 'Wood', '木', '우드', 'Madera') },
  { id: 'marble' as const,    label: L('大理石', 'Marble', '大理石', '대리석', 'Mármol') },
  { id: 'concrete' as const,  label: L('清水模', 'Concrete', 'コンクリート', '콘크리트', 'Hormigón') },
  { id: 'linen' as const,     label: L('亞麻', 'Linen', 'リネン', '리넨', 'Lino') },
  { id: 'brass' as const,     label: L('黃銅', 'Brass', '真鍮', '황동', 'Latón') },
  { id: 'leather' as const,   label: L('皮革', 'Leather', 'レザー', '가죽', 'Cuero') },
  { id: 'terrazzo' as const,  label: L('水磨石', 'Terrazzo', 'テラゾー', '테라조', 'Terrazo') },
])

// Checkbox proxy: off = auto (0), on = a neutral 4000K starting point.
const tempEnabled = computed({
  get: () => colorTemperature.value > 0,
  set: (v: boolean) => { colorTemperature.value = v ? 4000 : 0 },
})

const tempFeel = computed(() => {
  const k = colorTemperature.value
  if (k <= 3000) return L('溫暖', 'Warm', '暖色', '따뜻함', 'Cálida')
  if (k <= 3800) return L('暖白', 'Warm white', '温白色', '온백색', 'Blanco cálido')
  if (k <= 4800) return L('自然白', 'Neutral', '自然白', '주백색', 'Neutra')
  if (k <= 5800) return L('日光白', 'Daylight', '昼光色', '주광색', 'Luz día')
  return L('冷白', 'Cool', '寒色', '차가움', 'Fría')
})
</script>

<template>
  <div>
    <label class="pp-field-label">{{ L('光線氛圍', 'Lighting', 'ライティング', '조명 분위기', 'Iluminación') }}</label>
    <select v-model="lightingTone" class="pp-select">
      <option v-for="o in lightingOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
    </select>
  </div>

  <div>
    <label class="pp-field-label flex items-center justify-between">
      <span>
        {{ L('色溫', 'Color Temperature', '色温度', '색온도', 'Temperatura de color') }}
        <span v-if="tempEnabled" class="ml-2" style="color:#a78bfa">{{ colorTemperature }}K · {{ tempFeel }}</span>
        <span v-else class="ml-2" style="color:#6b6b7a">{{ L('自動', 'Auto', '自動', '자동', 'Auto') }}</span>
      </span>
      <input type="checkbox" v-model="tempEnabled" style="accent-color:#a78bfa; width:16px; height:16px;" />
    </label>
    <template v-if="tempEnabled">
      <input type="range" min="2700" max="6500" step="100" v-model.number="colorTemperature" class="w-full" style="accent-color:#a78bfa" />
      <div class="flex justify-between pp-field-help" style="margin-top:2px;">
        <span>{{ L('2700K 暖黃', '2700K warm', '2700K 暖色', '2700K 따뜻', '2700K cálida') }}</span>
        <span>{{ L('6500K 冷白', '6500K cool', '6500K 寒色', '6500K 차가움', '6500K fría') }}</span>
      </div>
    </template>
  </div>

  <div>
    <label class="pp-field-label">{{ L('主要材質（選填）', 'Material accent (optional)', 'アクセント素材（任意）', '주요 재질 (선택)', 'Material (opcional)') }}</label>
    <select v-model="materialAccent" class="pp-select">
      <option v-for="o in materialOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
    </select>
  </div>
</template>

<style scoped>
/* PiapiPlayground styles its slot content via :slotted(.pp-*), which does
   not reach inside nested components — so the same rules are replicated
   here. Keep in sync with PiapiPlayground.vue. */
.pp-field-label {
  display: block;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #94949f;
  margin-bottom: 0.4rem;
}
.pp-field-help {
  font-size: 0.7rem;
  color: #6b6b7a;
  margin-top: 0.25rem;
}
.pp-select {
  width: 100%;
  padding: 0.625rem 0.75rem;
  font-size: 0.875rem;
  color: #f5f5fa;
  background: #0a0a0f;
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 0.5rem;
  outline: none;
  transition: border-color 0.15s;
}
.pp-select:focus {
  border-color: #7c3aed;
}
</style>
