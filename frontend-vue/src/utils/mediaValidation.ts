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