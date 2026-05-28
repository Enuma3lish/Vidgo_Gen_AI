/**
 * Convert a `data:` URI to a Blob so we can upload the bytes via
 * multipart/form-data. Returns null when the input isn't a data URI we
 * can parse (corrupted base64, non-data scheme, etc.) so callers can
 * surface a clear "image format invalid" error instead of crashing.
 *
 * Extracted from views/tools/TryOn.vue (2026-05-24 refactor) so the
 * PiAPI-style refactor of every tool can import it from one place
 * instead of duplicating the function across .vue files.
 */
export function dataURItoBlob(dataURI: string): Blob | null {
  if (!dataURI || !dataURI.includes(',') || !dataURI.startsWith('data:')) {
    return null
  }
  try {
    const byteString = atob(dataURI.split(',')[1])
    const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0]
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    return new Blob([ab], { type: mimeString })
  } catch {
    return null
  }
}
