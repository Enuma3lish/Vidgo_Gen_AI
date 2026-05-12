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
