import type { WsMessage } from '../api/types'

type Handler = (msg: WsMessage) => void

export function createWsConnection(token: string, onMessage: Handler): () => void {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  let ws: WebSocket
  let reconnectTimer: ReturnType<typeof setTimeout>

  function connect() {
    // En prod: VITE_API_URL=https://backend.railway.app → wss://backend.railway.app/live-feed
    const apiOrigin = import.meta.env.VITE_API_URL as string | undefined
    const wsBase = apiOrigin
      ? apiOrigin.replace(/^https?/, proto)
      : `${proto}://${location.host}`
    ws = new WebSocket(`${wsBase}/live-feed?token=${encodeURIComponent(token)}`)

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data) as WsMessage
        onMessage(msg)
      } catch { /* ignore malformed */ }
    }

    ws.onclose = () => {
      reconnectTimer = setTimeout(connect, 3000)
    }
  }

  connect()

  return () => {
    clearTimeout(reconnectTimer)
    ws?.close()
  }
}
