<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'

interface Props {
  modelUrl: string
  width?: number
  height?: number
}

const props = withDefaults(defineProps<Props>(), {
  width: 600,
  height: 400
})

const containerRef = ref<HTMLDivElement | null>(null)
const loading = ref(true)
const loadError = ref('')

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let animationFrameId: number | null = null
let currentModel: THREE.Group | null = null

function initScene() {
  if (!containerRef.value) return

  // Scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a2e)

  // Camera
  camera = new THREE.PerspectiveCamera(45, props.width / props.height, 0.1, 1000)
  camera.position.set(3, 2, 3)

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(props.width, props.height)
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  containerRef.value.appendChild(renderer.domElement)

  // Controls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.autoRotate = true
  controls.autoRotateSpeed = 1.5
  controls.maxPolarAngle = Math.PI / 1.8
  controls.minDistance = 1
  controls.maxDistance = 20

  // Pause auto-rotate on user interaction
  controls.addEventListener('start', () => {
    if (controls) controls.autoRotate = false
  })
  controls.addEventListener('end', () => {
    // Resume auto-rotate after 3 seconds of inactivity
    setTimeout(() => {
      if (controls) controls.autoRotate = true
    }, 3000)
  })

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(5, 8, 5)
  directionalLight.castShadow = true
  directionalLight.shadow.mapSize.width = 1024
  directionalLight.shadow.mapSize.height = 1024
  scene.add(directionalLight)

  const fillLight = new THREE.DirectionalLight(0x8888ff, 0.3)
  fillLight.position.set(-3, 2, -3)
  scene.add(fillLight)

  // Grid floor helper
  const gridHelper = new THREE.GridHelper(10, 20, 0x444466, 0x333355)
  scene.add(gridHelper)

  // Start animation loop
  animate()
}

function animate() {
  animationFrameId = requestAnimationFrame(animate)
  if (controls) controls.update()
  if (renderer && scene && camera) {
    renderer.render(scene, camera)
  }
}

function loadModel(url: string) {
  if (!scene || !camera) return

  loading.value = true
  loadError.value = ''

  // Remove existing model
  if (currentModel) {
    scene.remove(currentModel)
    currentModel = null
  }

  const loader = new GLTFLoader()
  loader.load(
    url,
    (gltf) => {
      if (!scene || !camera) return

      currentModel = gltf.scene

      // Center and scale the model
      const box = new THREE.Box3().setFromObject(currentModel)
      const center = box.getCenter(new THREE.Vector3())
      const size = box.getSize(new THREE.Vector3())

      const maxDim = Math.max(size.x, size.y, size.z)
      const scale = 2 / maxDim
      currentModel.scale.setScalar(scale)

      // Re-center after scaling
      const scaledBox = new THREE.Box3().setFromObject(currentModel)
      const scaledCenter = scaledBox.getCenter(new THREE.Vector3())
      currentModel.position.sub(scaledCenter)
      currentModel.position.y -= scaledBox.min.y // Place on grid

      currentModel.traverse((child) => {
        if (child instanceof THREE.Mesh) {
          child.castShadow = true
          child.receiveShadow = true
        }
      })

      scene.add(currentModel)

      // Adjust camera to fit model
      camera.position.set(3, 2, 3)
      if (controls) controls.target.set(0, size.y * scale / 2, 0)

      loading.value = false
    },
    undefined,
    (error) => {
      loading.value = false
      loadError.value = error instanceof Error ? error.message : 'Failed to load 3D model'
    }
  )
}

function cleanup() {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId)
    animationFrameId = null
  }

  if (controls) {
    controls.dispose()
    controls = null
  }

  if (renderer) {
    renderer.dispose()
    if (containerRef.value && renderer.domElement.parentElement === containerRef.value) {
      containerRef.value.removeChild(renderer.domElement)
    }
    renderer = null
  }

  if (scene) {
    scene.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        object.geometry.dispose()
        if (Array.isArray(object.material)) {
          object.material.forEach((m) => m.dispose())
        } else {
          object.material.dispose()
        }
      }
    })
    scene = null
  }

  camera = null
  currentModel = null
}

watch(() => props.modelUrl, (newUrl) => {
  if (newUrl) loadModel(newUrl)
})

onMounted(() => {
  initScene()
  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }
})

onBeforeUnmount(() => {
  cleanup()
})
</script>

<template>
  <div class="relative inline-block rounded-xl overflow-hidden bg-dark-900 border border-dark-600">
    <!-- Three.js container -->
    <div
      ref="containerRef"
      :style="{ width: `${width}px`, height: `${height}px` }"
      class="three-canvas-container"
    />

    <!-- Loading Overlay -->
    <div
      v-if="loading"
      class="absolute inset-0 flex flex-col items-center justify-center bg-dark-900/80 z-10"
    >
      <div class="w-10 h-10 border-3 border-primary-500 border-t-transparent rounded-full animate-spin mb-3" />
      <span class="text-sm text-gray-400">Loading 3D model...</span>
    </div>

    <!-- Error Overlay -->
    <div
      v-if="loadError"
      class="absolute inset-0 flex flex-col items-center justify-center bg-dark-900/80 z-10"
    >
      <svg class="w-10 h-10 text-red-400 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      <span class="text-sm text-red-400 text-center px-4">{{ loadError }}</span>
    </div>

    <!-- Controls hint -->
    <div v-if="!loading && !loadError" class="absolute bottom-3 left-3 text-xs text-gray-500 bg-dark-900/70 px-2 py-1 rounded">
      Drag to rotate / Scroll to zoom
    </div>
  </div>
</template>

<style scoped>
.three-canvas-container :deep(canvas) {
  display: block;
}

.border-3 {
  border-width: 3px;
}
</style>
