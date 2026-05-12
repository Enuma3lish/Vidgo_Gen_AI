export interface ImageDimensionRule {
  label: string
  minWidth: number
  minHeight: number
  maxWidth: number
  maxHeight: number
  maxMegapixels: number
  minAspectRatio: number
  maxAspectRatio: number
  guidance: string
  guidanceZh: string
}

export const commonImageDimensionRule: ImageDimensionRule = {
  label: 'Image',
  minWidth: 128,
  minHeight: 128,
  maxWidth: 4096,
  maxHeight: 4096,
  maxMegapixels: 16,
  minAspectRatio: 0.25,
  maxAspectRatio: 4,
  guidance: 'Please choose an image between 128px and 4096px on each side.',
  guidanceZh: '請選擇每邊介於 128px 到 4096px 的圖片。',
}

const toolRules: Record<string, ImageDimensionRule> = {
  background_removal: commonImageDimensionRule,
  product_scene: {
    ...commonImageDimensionRule,
    label: 'Product scene input',
    minWidth: 256,
    minHeight: 256,
    guidance: 'Please choose a clear product image between 256px and 4096px on each side.',
    guidanceZh: '請選擇清楚的商品圖片，每邊需介於 256px 到 4096px。',
  },
  try_on: {
    ...commonImageDimensionRule,
    label: 'Try-on garment input',
    minWidth: 256,
    minHeight: 256,
    minAspectRatio: 0.5,
    maxAspectRatio: 2,
    guidance: 'Please choose a clear garment image, not an extreme panorama.',
    guidanceZh: '請選擇清楚的服飾圖片，避免過長或過窄的圖片。',
  },
  room_redesign: {
    ...commonImageDimensionRule,
    label: 'Room redesign input',
    minWidth: 512,
    minHeight: 512,
    minAspectRatio: 0.5,
    maxAspectRatio: 2.2,
    guidance: 'Please choose a room photo at least 512px on each side, not an extreme panorama.',
    guidanceZh: '請選擇每邊至少 512px 的空間照片，避免過長或過窄的圖片。',
  },
  short_video: {
    ...commonImageDimensionRule,
    label: 'Short video input',
    minWidth: 256,
    minHeight: 256,
    minAspectRatio: 0.45,
    maxAspectRatio: 2.2,
    guidance: 'Please choose an image close to 16:9, 1:1, or 9:16.',
    guidanceZh: '請選擇接近 16:9、1:1 或 9:16 的圖片。',
  },
  ai_avatar: {
    ...commonImageDimensionRule,
    label: 'AI avatar headshot',
    minWidth: 256,
    minHeight: 256,
    minAspectRatio: 0.75,
    maxAspectRatio: 1.25,
    guidance: 'Please choose a square or near-square head-and-shoulders portrait; full-body photos are rejected by the avatar API.',
    guidanceZh: '請選擇正方形或接近正方形的半身頭像；全身照會被 avatar API 拒絕。',
  },
  pattern_generate: commonImageDimensionRule,
  effect: commonImageDimensionRule,
  upscale: {
    ...commonImageDimensionRule,
    label: 'Upscale input',
    // Cap pre-upscale dimensions so 2x/4x doesn't blow past the
    // PiAPI image-toolkit 8 MP output ceiling. 2048x2048 in → 4096 at 2x.
    maxWidth: 2048,
    maxHeight: 2048,
    maxMegapixels: 4,
    guidance: 'Please choose an image up to 2048px on each side (4 MP).',
    guidanceZh: '請選擇每邊最大 2048px（4 MP）的圖片。',
  },
  image_translator: {
    ...commonImageDimensionRule,
    label: 'Image translation input',
    minWidth: 256,
    minHeight: 256,
    guidance: 'Please choose a clear image with readable text, at least 256px on each side.',
    guidanceZh: '請選擇文字清楚可讀、每邊至少 256px 的圖片。',
  },
}

export function imageDimensionRuleForTool(toolType?: string): ImageDimensionRule {
  return toolRules[toolType || ''] || commonImageDimensionRule
}

export function imageDimensions(file: File): Promise<{ width: number; height: number }> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      const width = image.naturalWidth
      const height = image.naturalHeight
      URL.revokeObjectURL(url)
      resolve({ width, height })
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('Image dimensions could not be read.'))
    }
    image.src = url
  })
}

function imageTypeFromFile(file: File): string | null {
  const type = (file.type || '').toLowerCase()
  if (ALLOWED_IMAGE_MIME.includes(type)) return type

  const lowerName = (file.name || '').toLowerCase()
  if (/\.(jpe?g)$/.test(lowerName)) return 'image/jpeg'
  if (/\.png$/.test(lowerName)) return 'image/png'
  if (/\.webp$/.test(lowerName)) return 'image/webp'
  return null
}

export function isAllowedImageFile(file: File): boolean {
  return Boolean(imageTypeFromFile(file))
}

function dimensionsAreWithinRule(width: number, height: number, rule: ImageDimensionRule): boolean {
  if (width < rule.minWidth || height < rule.minHeight) return false
  if (width > rule.maxWidth || height > rule.maxHeight) return false
  if ((width * height) / 1_000_000 > rule.maxMegapixels) return false

  const aspectRatio = width / height
  return aspectRatio >= rule.minAspectRatio && aspectRatio <= rule.maxAspectRatio
}

function normalizedImageName(name: string, mimeType: string): string {
  const extension = mimeType === 'image/png' ? 'png' : mimeType === 'image/webp' ? 'webp' : 'jpg'
  const baseName = (name || 'vidgo-upload').replace(/\.[^/.]+$/, '') || 'vidgo-upload'
  return `${baseName}.${extension}`
}

function canvasToBlob(canvas: HTMLCanvasElement, mimeType: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(blob => {
      if (blob) resolve(blob)
      else reject(new Error('Image could not be compressed.'))
    }, mimeType, quality)
  })
}

function downscaleCanvas(source: HTMLCanvasElement, ratio: number): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(source.width * ratio))
  canvas.height = Math.max(1, Math.round(source.height * ratio))
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Image could not be processed.')
  context.imageSmoothingEnabled = true
  context.imageSmoothingQuality = 'high'
  context.drawImage(source, 0, 0, canvas.width, canvas.height)
  return canvas
}

async function encodeCanvasWithinLimit(
  sourceCanvas: HTMLCanvasElement,
  preferredType: string,
  maxBytes: number,
): Promise<{ blob: Blob; mimeType: string }> {
  let canvas = sourceCanvas
  let mimeType = preferredType
  const qualityTypes = new Set(['image/jpeg', 'image/webp'])
  const qualities = qualityTypes.has(mimeType) ? [0.9, 0.82, 0.74, 0.66] : [undefined]
  let blob = await canvasToBlob(canvas, mimeType, qualities[0])

  for (const quality of qualities.slice(1)) {
    if (blob.size <= maxBytes) break
    blob = await canvasToBlob(canvas, mimeType, quality)
  }

  if (blob.size > maxBytes && mimeType === 'image/png') {
    mimeType = 'image/webp'
    for (const quality of [0.9, 0.82, 0.74, 0.66]) {
      blob = await canvasToBlob(canvas, mimeType, quality)
      if (blob.size <= maxBytes) break
    }
  }

  for (let attempt = 0; blob.size > maxBytes && attempt < 5; attempt += 1) {
    const ratio = Math.max(0.5, Math.sqrt(maxBytes / blob.size) * 0.92)
    canvas = downscaleCanvas(canvas, ratio)
    const retryQualities = qualityTypes.has(mimeType) ? [0.82, 0.74, 0.66] : [undefined]
    for (const quality of retryQualities) {
      blob = await canvasToBlob(canvas, mimeType, quality)
      if (blob.size <= maxBytes) break
    }
  }

  if (blob.size > maxBytes) {
    throw new Error('Image could not be compressed below the upload limit.')
  }

  return { blob, mimeType }
}

function targetFrameForRule(width: number, height: number, rule: ImageDimensionRule) {
  const sourceAspect = width / height
  let frameWidth = width
  let frameHeight = height

  if (sourceAspect < rule.minAspectRatio) {
    frameWidth = height * rule.minAspectRatio
  } else if (sourceAspect > rule.maxAspectRatio) {
    frameHeight = width / rule.maxAspectRatio
  }

  let scale = 1
  const minScale = Math.max(rule.minWidth / frameWidth, rule.minHeight / frameHeight)
  if (minScale > 1) scale = minScale

  const maxScale = Math.min(
    rule.maxWidth / frameWidth,
    rule.maxHeight / frameHeight,
    Math.sqrt((rule.maxMegapixels * 1_000_000) / (frameWidth * frameHeight)),
  )
  if (maxScale < scale || maxScale < 1) scale = maxScale

  const targetWidth = Math.max(1, Math.round(frameWidth * scale))
  const targetHeight = Math.max(1, Math.round(frameHeight * scale))
  const drawWidth = Math.max(1, Math.round(width * scale))
  const drawHeight = Math.max(1, Math.round(height * scale))

  return { targetWidth, targetHeight, drawWidth, drawHeight }
}

export async function normalizeImageFileForUpload(
  file: File,
  rule: ImageDimensionRule = commonImageDimensionRule,
  options: { maxSizeMb?: number } = {},
): Promise<File> {
  const preferredType = imageTypeFromFile(file)
  if (!preferredType) throw new Error(`Unsupported image format. Please re-upload as ${ALLOWED_IMAGE_EXT_LABEL}.`)

  const maxBytes = (options.maxSizeMb ?? MAX_IMAGE_SIZE_MB) * 1024 * 1024
  const url = URL.createObjectURL(file)

  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image()
      element.onload = () => resolve(element)
      element.onerror = () => reject(new Error('Image dimensions could not be read.'))
      element.src = url
    })

    const width = image.naturalWidth
    const height = image.naturalHeight
    if (dimensionsAreWithinRule(width, height, rule) && file.size <= maxBytes) {
      return file
    }

    const { targetWidth, targetHeight, drawWidth, drawHeight } = targetFrameForRule(width, height, rule)
    const canvas = document.createElement('canvas')
    canvas.width = targetWidth
    canvas.height = targetHeight
    const context = canvas.getContext('2d')
    if (!context) throw new Error('Image could not be processed.')

    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    if (preferredType === 'image/jpeg') {
      context.fillStyle = '#ffffff'
      context.fillRect(0, 0, targetWidth, targetHeight)
    } else {
      context.clearRect(0, 0, targetWidth, targetHeight)
    }

    const drawX = Math.round((targetWidth - drawWidth) / 2)
    const drawY = Math.round((targetHeight - drawHeight) / 2)
    context.drawImage(image, drawX, drawY, drawWidth, drawHeight)

    const { blob, mimeType } = await encodeCanvasWithinLimit(canvas, preferredType, maxBytes)
    return new File([blob], normalizedImageName(file.name, mimeType), {
      type: mimeType,
      lastModified: Date.now(),
    })
  } finally {
    URL.revokeObjectURL(url)
  }
}

export async function validateImageFileDimensions(
  file: File,
  rule: ImageDimensionRule = commonImageDimensionRule,
  isZh = false,
): Promise<string | null> {
  const { width, height } = await imageDimensions(file)
  const guidance = isZh ? rule.guidanceZh : rule.guidance
  const label = isZh ? '圖片' : rule.label
  const size = `${width}x${height}`

  if (width < rule.minWidth || height < rule.minHeight) {
    return isZh
      ? `${label} 尺寸為 ${size}，小於最低要求 ${rule.minWidth}x${rule.minHeight}。${guidance}`
      : `${label} is ${size}, smaller than the required ${rule.minWidth}x${rule.minHeight}. ${guidance}`
  }
  if (width > rule.maxWidth || height > rule.maxHeight) {
    return isZh
      ? `${label} 尺寸為 ${size}，超過最高限制 ${rule.maxWidth}x${rule.maxHeight}。${guidance}`
      : `${label} is ${size}, larger than the ${rule.maxWidth}x${rule.maxHeight} limit. ${guidance}`
  }

  const megapixels = (width * height) / 1_000_000
  if (megapixels > rule.maxMegapixels) {
    return isZh
      ? `${label} 尺寸為 ${size}，像素過高（${megapixels.toFixed(1)} MP）。${guidance}`
      : `${label} is ${size}, too large (${megapixels.toFixed(1)} MP). ${guidance}`
  }

  const aspectRatio = width / height
  if (aspectRatio < rule.minAspectRatio || aspectRatio > rule.maxAspectRatio) {
    return isZh
      ? `${label} 尺寸為 ${size}，比例不支援。${guidance}`
      : `${label} is ${size}, with an unsupported aspect ratio. ${guidance}`
  }
  return null
}

// =====================================================================
// Video upload validation
// =====================================================================

export const ALLOWED_IMAGE_MIME = ['image/jpeg', 'image/png', 'image/webp']
export const ALLOWED_IMAGE_EXT_LABEL = 'JPG / PNG / WebP'
export const MAX_IMAGE_SIZE_MB = 20

export const ALLOWED_VIDEO_MIME = [
  'video/mp4',
  'video/webm',
  'video/quicktime', // .mov
  'video/x-quicktime',
]
export const ALLOWED_VIDEO_EXT_LABEL = 'MP4 / WebM / MOV'
export const MAX_VIDEO_SIZE_MB = 100

export interface VideoValidationOptions {
  maxSizeMb?: number
}

/**
 * Validate a video file's MIME type and size before upload.
 * Returns a bilingual, "please re-upload as ..." style message when invalid,
 * or null when the file is acceptable. Falls back to file-extension sniffing
 * when the browser doesn't fill in `file.type`.
 */
export interface VideoNormalizeOptions {
  maxSizeMb?: number
  maxResolution?: number // longest edge, e.g. 720
  onProgress?: (ratio: number) => void
}

export interface VideoNormalizeResult {
  file: File
  normalized: boolean
  reason?: string
}

/**
 * Read basic metadata (duration + dimensions) from a video File without
 * playing it through. Returns null on decode failure.
 */
function readVideoMetadata(
  file: File,
): Promise<{ duration: number; width: number; height: number } | null> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    video.preload = 'metadata'
    video.muted = true
    video.src = url
    video.onloadedmetadata = () => {
      const data = {
        duration: video.duration,
        width: video.videoWidth,
        height: video.videoHeight,
      }
      URL.revokeObjectURL(url)
      resolve(data)
    }
    video.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(null)
    }
  })
}

/**
 * Browser-side video auto-resize. Mirrors normalizeImageFileForUpload for
 * videos: if the file is over budget (size or resolution), re-encode it
 * through Canvas + MediaRecorder so backend providers don't reject the
 * upload as too large. Returns the original File when it's already within
 * budget so we don't waste user time on a re-encode they didn't need.
 *
 * Caveats vs. server-side ffmpeg:
 *   - Re-encoding plays the source in real time (1×) — a 60 s video takes
 *     ~60 s to normalize. We surface progress via onProgress.
 *   - Output is WebM/VP8 or WebM/VP9 (whatever the browser supports). Our
 *     backend already accepts video/webm, so this is fine.
 *   - On browsers that don't expose HTMLMediaElement.captureStream() we
 *     fall back to returning the original file with `normalized: false`
 *     and the caller decides whether to reject or accept it.
 */
export async function normalizeVideoFileForUpload(
  file: File,
  opts: VideoNormalizeOptions = {},
): Promise<VideoNormalizeResult> {
  const maxBytes = (opts.maxSizeMb ?? MAX_VIDEO_SIZE_MB) * 1024 * 1024
  const maxResolution = opts.maxResolution ?? 1080

  const meta = await readVideoMetadata(file)
  if (!meta) {
    return { file, normalized: false, reason: 'metadata_decode_failed' }
  }

  const currentMaxDim = Math.max(meta.width, meta.height)
  if (file.size <= maxBytes && currentMaxDim <= maxResolution) {
    return { file, normalized: false }
  }

  // Capability checks. Without canvas.captureStream + MediaRecorder we
  // can't re-encode in the browser; tell the caller and let the existing
  // size-error path show its message.
  const hasMR = typeof MediaRecorder !== 'undefined'
  if (!hasMR || typeof (document.createElement('canvas') as any).captureStream !== 'function') {
    return { file, normalized: false, reason: 'browser_unsupported' }
  }

  const url = URL.createObjectURL(file)
  const video = document.createElement('video')
  video.src = url
  video.muted = true
  ;(video as any).playsInline = true
  video.crossOrigin = 'anonymous'

  await new Promise<void>((resolve, reject) => {
    video.onloadedmetadata = () => resolve()
    video.onerror = () => reject(new Error('Video could not be loaded for re-encoding.'))
  })

  const duration = video.duration
  const scale = Math.min(1, maxResolution / currentMaxDim)
  // libx264 / VP8 expect even dimensions; round down to nearest 2.
  const targetW = Math.max(2, Math.floor((meta.width * scale) / 2) * 2)
  const targetH = Math.max(2, Math.floor((meta.height * scale) / 2) * 2)

  const canvas = document.createElement('canvas')
  canvas.width = targetW
  canvas.height = targetH
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    URL.revokeObjectURL(url)
    return { file, normalized: false, reason: 'canvas_unavailable' }
  }

  const videoStream = (canvas as any).captureStream(30) as MediaStream

  // Try to pull the audio track from the source video via the standard
  // HTMLMediaElement.captureStream(). On Safari this may throw or return
  // a stream without audio tracks; if so we record video-only.
  try {
    const elementStream: MediaStream | undefined =
      typeof (video as any).captureStream === 'function'
        ? (video as any).captureStream()
        : typeof (video as any).mozCaptureStream === 'function'
          ? (video as any).mozCaptureStream()
          : undefined
    if (elementStream) {
      for (const audioTrack of elementStream.getAudioTracks()) {
        videoStream.addTrack(audioTrack)
      }
    }
  } catch {
    /* video-only re-encode is still better than rejecting the upload */
  }

  const mimeCandidates = [
    'video/webm;codecs=vp9,opus',
    'video/webm;codecs=vp8,opus',
    'video/webm',
  ]
  const mimeType = mimeCandidates.find((m) => MediaRecorder.isTypeSupported(m)) || 'video/webm'

  // Target ~75 % of byte budget so muxing overhead doesn't bust the cap.
  const safeDuration = Math.max(1, duration || 0)
  const targetBitsPerSecond = Math.max(
    400_000,
    Math.min(2_500_000, Math.floor((maxBytes * 8 * 0.75) / safeDuration)),
  )

  const recorder = new MediaRecorder(videoStream, {
    mimeType,
    videoBitsPerSecond: targetBitsPerSecond,
    audioBitsPerSecond: 128_000,
  })

  const chunks: Blob[] = []
  recorder.ondataavailable = (e) => {
    if (e.data && e.data.size > 0) chunks.push(e.data)
  }

  const stopped = new Promise<void>((resolve) => {
    recorder.onstop = () => resolve()
  })

  let running = true
  const drawFrame = () => {
    if (!running) return
    try {
      ctx.drawImage(video, 0, 0, targetW, targetH)
    } catch {
      /* ignore intermittent draw errors near seek boundaries */
    }
    if (typeof opts.onProgress === 'function' && safeDuration > 0) {
      opts.onProgress(Math.min(1, video.currentTime / safeDuration))
    }
    requestAnimationFrame(drawFrame)
  }

  recorder.start(1000)
  try {
    video.currentTime = 0
    await video.play()
  } catch (err) {
    running = false
    try { recorder.stop() } catch {}
    URL.revokeObjectURL(url)
    return { file, normalized: false, reason: 'playback_blocked' }
  }
  drawFrame()

  await new Promise<void>((resolve) => {
    video.onended = () => resolve()
  })
  running = false
  try { recorder.stop() } catch {}
  await stopped
  URL.revokeObjectURL(url)

  const blob = new Blob(chunks, { type: mimeType })
  if (blob.size === 0) {
    return { file, normalized: false, reason: 'recorder_empty' }
  }
  const newName = file.name.replace(/\.[^.]+$/, '') + '.webm'
  const outFile = new File([blob], newName, { type: mimeType, lastModified: Date.now() })
  return { file: outFile, normalized: true }
}


export function validateVideoFile(
  file: File,
  isZh = false,
  opts: VideoValidationOptions = {},
): string | null {
  const maxSizeMb = opts.maxSizeMb ?? MAX_VIDEO_SIZE_MB
  const maxBytes = maxSizeMb * 1024 * 1024

  const lowerName = (file.name || '').toLowerCase()
  const extOk = /\.(mp4|webm|mov)$/.test(lowerName)
  const typeOk = file.type ? ALLOWED_VIDEO_MIME.includes(file.type) : false

  if (!typeOk && !extOk) {
    return isZh
      ? `不支援的影片格式，請改用 ${ALLOWED_VIDEO_EXT_LABEL} 格式重新上傳。`
      : `Unsupported video format. Please re-upload as ${ALLOWED_VIDEO_EXT_LABEL}.`
  }

  if (file.size > maxBytes) {
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1)
    return isZh
      ? `影片大小 ${sizeMB}MB 超過上限 ${maxSizeMb}MB，請壓縮或裁短後重新上傳 ${ALLOWED_VIDEO_EXT_LABEL}。`
      : `Video size ${sizeMB}MB exceeds the ${maxSizeMb}MB limit. Please compress or trim and re-upload as ${ALLOWED_VIDEO_EXT_LABEL}.`
  }

  return null
}

/**
 * Build a short, human-readable hint string describing what kind of image
 * a given tool expects. Used in the "How to use" hint card so users know
 * the format requirements before they pick a file.
 *
 * Accepts either a locale code string ('en' | 'zh-TW' | 'ja' | 'ko' | 'es')
 * or a boolean (legacy isZh). New callers should pass the locale code.
 */
type LocaleArg = string | boolean
function toLocale(value: LocaleArg): 'en' | 'zh' | 'ja' | 'ko' | 'es' {
  if (typeof value === 'boolean') return value ? 'zh' : 'en'
  const v = (value || '').toLowerCase()
  if (v.startsWith('zh')) return 'zh'
  if (v.startsWith('ja')) return 'ja'
  if (v.startsWith('ko')) return 'ko'
  if (v.startsWith('es')) return 'es'
  return 'en'
}

export function imageHintForTool(toolType: string | undefined, localeArg: LocaleArg = 'en'): string {
  imageDimensionRuleForTool(toolType)
  const loc = toLocale(localeArg)
  if (loc === 'zh') return `${ALLOWED_IMAGE_EXT_LABEL}。系統會自動調整尺寸與壓縮後再送出。`
  if (loc === 'ja') return `${ALLOWED_IMAGE_EXT_LABEL}。アップロード前に画像は自動でリサイズ・圧縮されます。`
  if (loc === 'ko') return `${ALLOWED_IMAGE_EXT_LABEL}. 업로드 전에 이미지가 자동으로 크기 조정 및 압축됩니다.`
  if (loc === 'es') return `${ALLOWED_IMAGE_EXT_LABEL}. Las imágenes se redimensionan y comprimen automáticamente antes de subirlas.`
  return `${ALLOWED_IMAGE_EXT_LABEL}. Images are resized and compressed automatically before upload.`
}

export function videoHintForTool(_toolType: string | undefined, localeArg: LocaleArg = 'en'): string {
  const loc = toLocale(localeArg)
  if (loc === 'zh') return `${ALLOWED_VIDEO_EXT_LABEL}，最大 ${MAX_VIDEO_SIZE_MB}MB。`
  if (loc === 'ja') return `${ALLOWED_VIDEO_EXT_LABEL}、最大 ${MAX_VIDEO_SIZE_MB}MB。`
  if (loc === 'ko') return `${ALLOWED_VIDEO_EXT_LABEL}, 최대 ${MAX_VIDEO_SIZE_MB}MB.`
  if (loc === 'es') return `${ALLOWED_VIDEO_EXT_LABEL}, hasta ${MAX_VIDEO_SIZE_MB}MB.`
  return `${ALLOWED_VIDEO_EXT_LABEL}, up to ${MAX_VIDEO_SIZE_MB}MB.`
}
