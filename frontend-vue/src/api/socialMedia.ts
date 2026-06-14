/**
 * Client-side social sharing helpers.
 * VidGo shares work links by opening platform share/upload destinations; no OAuth
 * account connection or server-side publishing is required.
 */

export type SocialShareMode = 'direct_share' | 'copy_first'

export interface SocialSharePlatform {
  id: string
  name: string
  icon: string
  color: string
  mode: SocialShareMode
  supportsImage: boolean
  supportsVideo: boolean
  destinationUrl?: string
}

export const socialSharePlatforms: SocialSharePlatform[] = [
  { id: 'facebook', name: 'Facebook', icon: 'f', color: '#1877f2', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'x', name: 'X', icon: 'X', color: '#e8f4ff', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'threads', name: 'Threads', icon: '@', color: '#e8f4ff', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'linkedin', name: 'LinkedIn', icon: 'in', color: '#0a66c2', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'line', name: 'LINE', icon: 'L', color: '#06c755', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'whatsapp', name: 'WhatsApp', icon: 'W', color: '#25d366', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'telegram', name: 'Telegram', icon: 'T', color: '#229ed9', mode: 'direct_share', supportsImage: true, supportsVideo: true },
  { id: 'instagram', name: 'Instagram', icon: 'IG', color: '#e1306c', mode: 'copy_first', supportsImage: true, supportsVideo: true, destinationUrl: 'https://www.instagram.com/' },
  { id: 'tiktok', name: 'TikTok', icon: '♪', color: '#e8f4ff', mode: 'copy_first', supportsImage: false, supportsVideo: true, destinationUrl: 'https://www.tiktok.com/upload' },
  { id: 'youtube', name: 'YouTube', icon: '▶', color: '#ff0000', mode: 'copy_first', supportsImage: false, supportsVideo: true, destinationUrl: 'https://studio.youtube.com/' },
]

export function buildSocialShareUrl(platform: SocialSharePlatform, workUrl: string, caption: string): string {
  const encodedUrl = encodeURIComponent(workUrl)
  const encodedCaption = encodeURIComponent(caption)
  const encodedCaptionWithUrl = encodeURIComponent(caption ? `${caption} ${workUrl}` : workUrl)

  switch (platform.id) {
    case 'facebook':
      return `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}`
    case 'x':
      return `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedCaption}`
    case 'threads':
      return `https://www.threads.net/intent/post?text=${encodedCaptionWithUrl}`
    case 'linkedin':
      return `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`
    case 'line':
      return `https://social-plugins.line.me/lineit/share?url=${encodedUrl}`
    case 'whatsapp':
      return `https://api.whatsapp.com/send?text=${encodedCaptionWithUrl}`
    case 'telegram':
      return `https://t.me/share/url?url=${encodedUrl}&text=${encodedCaption}`
    default:
      return platform.destinationUrl || workUrl
  }
}
