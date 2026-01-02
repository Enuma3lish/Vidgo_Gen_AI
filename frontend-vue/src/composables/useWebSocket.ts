import { ref, readonly, onUnmounted } from 'vue'

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

export interface UseWebSocketOptions {
  autoConnect?: boolean
  reconnect?: boolean
  reconnectInterval?: number
  maxReconnectAttempts?: number
  onMessage?: (data: any) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const {
    autoConnect = true,
    reconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    onMessage,
    onOpen,
    onClose,
    onError
  } = options

  const ws = ref<WebSocket | null>(null)
  const status = ref<WebSocketStatus>('disconnected')
  const lastMessage = ref<any>(null)
  const reconnectAttempts = ref(0)

  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) {
      return
    }

    status.value = 'connecting'

    try {
      ws.value = new WebSocket(url)

      ws.value.onopen = () => {
        status.value = 'connected'
        reconnectAttempts.value = 0
        onOpen?.()
      }

      ws.value.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          lastMessage.value = data
          onMessage?.(data)
        } catch {
          lastMessage.value = event.data
          onMessage?.(event.data)
        }
      }

      ws.value.onclose = () => {
        status.value = 'disconnected'
        onClose?.()

        if (reconnect && reconnectAttempts.value < maxReconnectAttempts) {
          scheduleReconnect()
        }
      }

      ws.value.onerror = (error) => {
        status.value = 'error'
        onError?.(error)
      }
    } catch (error) {
      status.value = 'error'
      if (reconnect && reconnectAttempts.value < maxReconnectAttempts) {
        scheduleReconnect()
      }
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    if (ws.value) {
      ws.value.close()
      ws.value = null
    }

    status.value = 'disconnected'
  }

  function send(data: any) {
    if (ws.value?.readyState === WebSocket.OPEN) {
      ws.value.send(typeof data === 'string' ? data : JSON.stringify(data))
      return true
    }
    return false
  }

  function scheduleReconnect() {
    if (reconnectTimer) return

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      reconnectAttempts.value++
      connect()
    }, reconnectInterval)
  }

  // Auto connect if enabled
  if (autoConnect) {
    connect()
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    ws: readonly(ws),
    status: readonly(status),
    lastMessage: readonly(lastMessage),
    reconnectAttempts: readonly(reconnectAttempts),
    connect,
    disconnect,
    send
  }
}
