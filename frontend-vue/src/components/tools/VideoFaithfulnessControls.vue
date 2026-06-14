<script setup lang="ts">
/**
 * VideoFaithfulnessControls — shared anti-hallucination controls for the
 * video tools (ShortVideo, KlingVideo, Sora2Pro).
 *
 * Because the platform never rewrites the user's prompt (owner directive
 * 2026-05-23: prompt-fidelity / verbatim), hallucination is reduced with
 * USER-CHOSEN additive levers instead:
 *   - cameraMove: a deterministic camera-move catalog (backend
 *     VIDEO_CAMERA_MOVES) so the model can't improvise a different move.
 *   - faithLock: one toggle whose meaning adapts to the mode —
 *       i2v → subject_lock  (keep the uploaded subject identical)
 *       t2v → strict_prompt (render only what the prompt describes)
 *     Default ON; users can switch it off for creative transformations.
 */
import { computed } from 'vue'
import { useLocalized } from '@/composables'

const props = defineProps<{ mode: 'i2v' | 't2v' }>()
const { L } = useLocalized()

const cameraMove = defineModel<string>('cameraMove', { default: '' })
const faithLock = defineModel<boolean>('faithLock', { default: true })

// Ids must match backend VIDEO_CAMERA_MOVES in app/api/v1/tools.py.
const cameraOptions = computed(() => [
  { id: '',          label: L('自動（由模型決定）', 'Auto (model decides)', '自動（モデル任せ）', '자동 (모델 결정)', 'Auto (decide el modelo)') },
  { id: 'static',    label: L('固定鏡頭（不移動）', 'Static (no camera move)', '固定カメラ', '고정 카메라', 'Cámara fija') },
  { id: 'dolly_in',  label: L('緩慢推近', 'Slow dolly-in', 'ゆっくり前進', '천천히 줌인', 'Dolly-in lento') },
  { id: 'dolly_out', label: L('緩慢拉遠', 'Slow pull-out', 'ゆっくり後退', '천천히 줌아웃', 'Alejamiento lento') },
  { id: 'orbit',     label: L('環繞拍攝', 'Orbit around subject', '周回ショット', '주위 회전', 'Órbita') },
  { id: 'pan',       label: L('水平橫移', 'Horizontal pan', '水平パン', '수평 팬', 'Paneo horizontal') },
  { id: 'tilt_up',   label: L('由下而上仰拍', 'Tilt-up reveal', 'ティルトアップ', '틸트업', 'Tilt-up') },
  { id: 'crane_up',  label: L('升降上升', 'Crane up', 'クレーンアップ', '크레인 업', 'Grúa ascendente') },
  { id: 'handheld',  label: L('輕微手持感', 'Subtle handheld', '軽い手持ち感', '약한 핸드헬드', 'Cámara en mano sutil') },
])

const lockLabel = computed(() => props.mode === 'i2v'
  ? L('主體保真鎖定', 'Subject Lock', '被写体ロック', '피사체 고정', 'Bloqueo del sujeto')
  : L('嚴格遵循提示詞', 'Strict Prompt Adherence', 'プロンプト厳守', '프롬프트 엄수', 'Adherencia estricta'))

const lockHelp = computed(() => props.mode === 'i2v'
  ? L(
      '確保上傳圖片中的主體（商品 / 人物）形狀、顏色、文字完全不變，不憑空新增物件、人物或文字。建議保持開啟。',
      'Keeps the uploaded subject (product / person) identical — same shape, colors and label text — and blocks the AI from adding objects, people, or text. Recommended on.',
      'アップロードした被写体の形・色・文字を完全に維持し、AIが勝手に物や人や文字を追加するのを防ぎます。オン推奨。',
      '업로드한 피사체의 형태·색상·문구를 그대로 유지하고, AI가 임의로 물체·인물·텍스트를 추가하는 것을 막습니다. 켜두기를 권장.',
      'Mantiene el sujeto idéntico y evita que la IA añada objetos, personas o texto. Recomendado activado.')
  : L(
      '只生成提示詞描述的內容，不添加未要求的物件、人物、字幕或標誌。建議保持開啟。',
      'Renders only what your prompt describes — no unrequested objects, characters, captions, or logos. Recommended on.',
      'プロンプトに書かれた内容だけを生成し、頼んでいない物・人・字幕・ロゴを追加しません。オン推奨。',
      '프롬프트에 적은 내용만 생성하고, 요청하지 않은 물체·인물·자막·로고를 추가하지 않습니다. 켜두기를 권장.',
      'Genera solo lo que describe tu prompt, sin objetos, personajes ni logos no pedidos. Recomendado activado.'))
</script>

<template>
  <div>
    <label class="pp-field-label">{{ L('鏡頭運動', 'Camera Move', 'カメラワーク', '카메라 움직임', 'Movimiento de cámara') }}</label>
    <select v-model="cameraMove" class="pp-select">
      <option v-for="o in cameraOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
    </select>
    <p class="pp-field-help">{{ L('指定明確的鏡頭運動，AI 不會自行發揮其他運鏡。', 'Pins an exact camera move so the AI can\'t improvise a different one.', '正確なカメラワークを固定し、AIの勝手な演出を防ぎます。', '정확한 카메라 움직임을 고정해 AI의 임의 연출을 막습니다.', 'Fija un movimiento exacto para que la IA no improvise otro.') }}</p>
  </div>

  <div>
    <label class="pp-field-label flex items-center justify-between">
      <span>{{ lockLabel }}</span>
      <input type="checkbox" v-model="faithLock" style="accent-color:#a78bfa; width:16px; height:16px;" />
    </label>
    <p class="pp-field-help">{{ lockHelp }}</p>
  </div>
</template>

<style scoped>
/* PiapiPlayground styles its slot content via :slotted(.pp-*), which does
   not reach inside nested components — so the same rules are replicated
   here (also makes this component usable on non-playground pages like
   KlingVideo / Sora2Pro). Keep in sync with PiapiPlayground.vue. */
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
