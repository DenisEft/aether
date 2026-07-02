import { ref, onUnmounted } from 'vue'
import { useAuthStore } from '../../stores/auth'
import type { WSMessage } from '../types/client'

export function useWebSocket(tenantSlug: string) {
  const connected = ref(false)
  const messages = ref<WSMessage[]>([])
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let pingInterval: ReturnType<typeof setInterval> | null = null

  function connect() {
    const auth = useAuthStore()
    const token = auth.accessToken
    if (!token || !tenantSlug) return

    const base = import.meta.env.VITE_WS_URL || 'ws://localhost:8799'
    ws = new WebSocket(`${base}/ws/widget/${tenantSlug}?token=${token}`)

    ws.onopen = () => {
      connected.value = true
      pingInterval = setInterval(() => {
        ws?.send(JSON.stringify({ type: 'pong' }))
      }, 25000)
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as WSMessage
        if (msg.type !== 'ping' && msg.type !== 'pong') {
          messages.value.push(msg)
        }
      } catch (e: unknown) {
        console.error('[useWebSocket] Failed to parse WebSocket message', e)
      }
    }

    ws.onclose = () => {
      connected.value = false
      if (pingInterval) clearInterval(pingInterval)
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  function send(msg: WSMessage) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg))
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (pingInterval) clearInterval(pingInterval)
    ws?.close()
  }

  onUnmounted(disconnect)

  return { connected, messages, connect, send, disconnect }
}
