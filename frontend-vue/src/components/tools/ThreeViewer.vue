<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

const props = withDefaults(defineProps<{
  modelUrl?: string
  autoRotate?: boolean
  width?: number
  height?: number
}>(), {
  autoRotate: true,
  width: 560,
  height: 400,
})

const containerRef = ref<HTMLDivElement | null>(null)
const loading = ref(false)
const error = ref('')

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let currentModel: THREE.Object3D | null = null
let frameId = 0

function disposeObject(object: THREE.Object3D) {
  object.traverse((child) => {
    const mesh = child as THREE.Mesh
    if (mesh.geometry) mesh.geometry.dispose()
    const material = mesh.material as THREE.Material | THREE.Material[] | undefined
    if (Array.isArray(material)) {
      material.forEach(item => item.dispose())
    } else if (material) {
      material.dispose()
    }
  })
}

function disposeScene() {
  if (frameId) cancelAnimationFrame(frameId)
  if (currentModel) disposeObject(currentModel)
  controls?.dispose()
  renderer?.dispose()
  renderer?.domElement.remove()
  renderer = null
  scene = null
  camera = null
  controls = null
  currentModel = null
  frameId = 0
}

function frameModel(model: THREE.Object3D) {
  if (!camera || !controls) return
  const box = new THREE.Box3().setFromObject(model)
  const size = box.getSize(new THREE.Vector3())
  const center = box.getCenter(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z) || 1
  const fov = camera.fov * (Math.PI / 180)
  const distance = Math.abs(maxDim / Math.sin(fov / 2)) * 0.75

  camera.position.set(center.x + distance, center.y + distance * 0.45, center.z + distance)
  camera.near = Math.max(0.01, distance / 100)
  camera.far = distance * 100
  camera.updateProjectionMatrix()
  controls.target.copy(center)
  controls.update()
}

function animate() {
  if (!renderer || !scene || !camera) return
  if (props.autoRotate && currentModel) currentModel.rotation.y += 0.004
  controls?.update()
  renderer.render(scene, camera)
  frameId = requestAnimationFrame(animate)
}

async function loadModel() {
  if (!containerRef.value || !props.modelUrl) return
  disposeScene()
  await nextTick()

  loading.value = true
  error.value = ''

  const width = containerRef.value.clientWidth || props.width
  const height = props.height
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x111827)

  camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000)
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  containerRef.value.appendChild(renderer.domElement)

  const ambient = new THREE.HemisphereLight(0xffffff, 0x334155, 2.4)
  scene.add(ambient)
  const key = new THREE.DirectionalLight(0xffffff, 2.2)
  key.position.set(3, 5, 4)
  scene.add(key)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true

  try {
    const loader = new GLTFLoader()
    const gltf = await loader.loadAsync(props.modelUrl)
    currentModel = gltf.scene
    scene.add(currentModel)
    frameModel(currentModel)
    animate()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to load 3D model'
  } finally {
    loading.value = false
  }
}

function handleResize() {
  if (!containerRef.value || !renderer || !camera) return
  const width = containerRef.value.clientWidth || props.width
  const height = props.height
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  loadModel()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeScene()
})

watch(() => props.modelUrl, loadModel)
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full overflow-hidden rounded-2xl"
    :style="{ height: `${height}px`, background: '#111827' }"
  >
    <div v-if="loading" class="absolute inset-0 flex items-center justify-center text-sm text-dark-300">
      Loading 3D model...
    </div>
    <div v-if="error" class="absolute inset-0 flex items-center justify-center px-4 text-center text-sm text-red-300">
      {{ error }}
    </div>
  </div>
</template>
