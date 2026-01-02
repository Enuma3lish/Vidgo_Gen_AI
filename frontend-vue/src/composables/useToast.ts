import { ref, readonly } from 'vue'

export interface Toast {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  message: string
  duration: number
}

const toasts = ref<Toast[]>([])
let nextId = 1

export function useToast() {
  function show(
    message: string,
    type: Toast['type'] = 'info',
    duration: number = 3000
  ) {
    const id = nextId++
    const toast: Toast = { id, type, message, duration }

    toasts.value.push(toast)

    if (duration > 0) {
      setTimeout(() => {
        remove(id)
      }, duration)
    }

    return id
  }

  function success(message: string, duration?: number) {
    return show(message, 'success', duration)
  }

  function error(message: string, duration?: number) {
    return show(message, 'error', duration)
  }

  function warning(message: string, duration?: number) {
    return show(message, 'warning', duration)
  }

  function info(message: string, duration?: number) {
    return show(message, 'info', duration)
  }

  function remove(id: number) {
    const index = toasts.value.findIndex(t => t.id === id)
    if (index > -1) {
      toasts.value.splice(index, 1)
    }
  }

  function clear() {
    toasts.value = []
  }

  return {
    toasts: readonly(toasts),
    show,
    success,
    error,
    warning,
    info,
    remove,
    clear
  }
}
