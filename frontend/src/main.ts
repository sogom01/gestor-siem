import './styles/main.css'
import { api } from './api/client'
import type { AlertOut, AgentOut, EventOut, WsMessage, TimelineBucket } from './api/types'
import { utcClock, timeAgo, formatSeconds } from './utils/time'
import { createWsConnection } from './utils/ws'
import { initTimeline, updateTimeline, pushTimelineEvent } from './charts/timeline'

// ── State ────────────────────────────────────────────────────────────
let token = sessionStorage.getItem('siem_token') ?? ''
let jwtExpiresIn = 0
let uptimeSeconds = 0
let wsDisconnect: (() => void) | null = null
let logTotal = 0

// Timeline state
let timelineData: TimelineBucket[] = []
let timelineMinutes = 60

// Log Explorer state
let explorerPage = 1
const explorerSize = 50
let explorerTotal = 0
let explorerFilters: { severity?: string; host?: string; date_from?: string; date_to?: string } = {}

const sparkData = {
  events: Array<number>(20).fill(0),
  alerts: Array<number>(20).fill(0),
  fail: Array<number>(20).fill(0),
  today: Array<number>(20).fill(0),
}

// ── DOM helpers ──────────────────────────────────────────────────────
const $ = <T extends HTMLElement>(sel: string) => document.querySelector<T>(sel)!

function setText(sel: string, val: string) {
  const el = $(sel)
  if (el) el.textContent = val
}

// ── Navegación entre vistas ──────────────────────────────────────────
const VIEWS = ['dashboard', 'logs'] as const
type View = typeof VIEWS[number]

function switchView(view: View) {
  document.querySelectorAll<HTMLElement>('[id^="view-"]').forEach(el => el.classList.add('hidden'))
  document.querySelectorAll<HTMLButtonElement>('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === view)
    btn.setAttribute('aria-current', btn.dataset.view === view ? 'page' : 'false')
  })
  $(`#view-${view}`).classList.remove('hidden')
  if (view === 'logs') loadExplorer()
}

document.querySelectorAll<HTMLButtonElement>('.nav-item[data-view]').forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view as View))
})

// ── Login ────────────────────────────────────────────────────────────
$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault()
  const btn = $<HTMLButtonElement>('#login-btn')
  const errEl = $('#login-error')
  const user = $<HTMLInputElement>('#login-user').value.trim()
  const pass = $<HTMLInputElement>('#login-pass').value

  errEl.textContent = ''
  btn.disabled = true
  btn.textContent = 'VERIFICANDO...'

  try {
    const res = await api.login(user, pass)
    token = res.access_token
    jwtExpiresIn = res.expires_in
    sessionStorage.setItem('siem_token', token)
    sessionStorage.setItem('siem_role', res.role)
    sessionStorage.setItem('siem_user', user)
    $('#login-overlay').classList.add('hidden')
    boot()
  } catch (err: unknown) {
    errEl.textContent = err instanceof Error ? err.message : 'Error de autenticación'
    btn.disabled = false
    btn.textContent = 'INICIAR SESIÓN'
  }
})

$('#btn-logout').addEventListener('click', () => {
  sessionStorage.clear()
  wsDisconnect?.()
  location.reload()
})

// ── Auto-login si hay token en sessionStorage ────────────────────────
if (token) {
  $('#login-overlay').classList.add('hidden')
  jwtExpiresIn = 3600
  boot()
}

// ── Boot ─────────────────────────────────────────────────────────────
async function boot() {
  const user = sessionStorage.getItem('siem_user') ?? '—'
  const role = sessionStorage.getItem('siem_role') ?? '—'
  setText('#session-user', user)
  setText('#jwt-role', role.toUpperCase())

  startClock()
  startUptime()
  startJwtCountdown()
  initTimeline($('#chart-timeline'))
  await loadAll()
  startPolling()
  connectWs()

  // Selector de rango del timeline
  $<HTMLSelectElement>('#timeline-range').addEventListener('change', (e) => {
    timelineMinutes = Number((e.target as HTMLSelectElement).value)
    loadTimeline()
  })
}

// ── Reloj UTC ─────────────────────────────────────────────────────────
function startClock() {
  function tick() { setText('#top-clock', utcClock()) }
  tick()
  setInterval(tick, 1000)
}

// ── Uptime ────────────────────────────────────────────────────────────
function startUptime() {
  function tick() {
    const d = Math.floor(uptimeSeconds / 86400)
    const h = Math.floor((uptimeSeconds % 86400) / 3600)
    const m = Math.floor((uptimeSeconds % 3600) / 60)
    setText('#sb-uptime', `${d}d ${h}h ${m}m`)
    uptimeSeconds++
  }
  tick()
  setInterval(tick, 1000)
}

// ── JWT countdown ────────────────────────────────────────────────────
function startJwtCountdown() {
  function tick() {
    setText('#jwt-countdown', formatSeconds(jwtExpiresIn))
    if (jwtExpiresIn > 0) jwtExpiresIn--
    else setText('#jwt-status', '⚠ EXPIRADO')
  }
  tick()
  setInterval(tick, 1000)
}

// ── Carga inicial de datos ────────────────────────────────────────────
async function loadAll() {
  await Promise.allSettled([loadStats(), loadAlerts(), loadAgents(), loadEvents(), loadTimeline()])
}

async function loadTimeline() {
  try {
    timelineData = await api.timeline(timelineMinutes)
    updateTimeline(timelineData)
  } catch { /* silencio */ }
}

// ── Stats ─────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const s = await api.stats()
    setText('#m-ev-hour', s.events_per_hour.toLocaleString())
    setText('#m-crit', String(s.critical_alerts_open))
    setText('#m-fail', String(s.failed_logins_hour))
    setText('#m-today', s.events_today.toLocaleString())
    setText('#sb-events', s.events_today.toLocaleString())

    const critCount = s.critical_alerts_open
    setText('#crit-label', `${critCount} ALERTAS CRÍTICAS`)
    setText('#alert-badge', `⚠ ${critCount} CRÍT`)
    setText('#nav-alert-badge', String(critCount))

    // Sparklines
    pushSpark(sparkData.events, s.events_per_hour)
    pushSpark(sparkData.fail, s.failed_logins_hour)
    pushSpark(sparkData.today, s.events_today)
    pushSpark(sparkData.alerts, s.critical_alerts_open)
    renderSparkline('#spark-events', sparkData.events)
    renderSparkline('#spark-fail', sparkData.fail)
    renderSparkline('#spark-today', sparkData.today)
    renderSparkline('#spark-alerts', sparkData.alerts)
  } catch { /* silencio en error de red */ }
}

// ── Alertas ───────────────────────────────────────────────────────────
async function loadAlerts() {
  try {
    const alerts = await api.activeAlerts()
    renderAlerts(alerts)
    const critCount = alerts.filter(a => a.severity === 'crit').length
    setText('#alerts-count-tag', `${critCount} CRÍTICAS`)
  } catch { /* silencio */ }
}

function renderAlerts(alerts: AlertOut[]) {
  const list = $('#alerts-list')
  list.innerHTML = ''
  if (!alerts.length) {
    list.innerHTML = '<div style="color:var(--text2);font-size:.65rem;padding:.75rem">// Sin alertas activas</div>'
    return
  }
  for (const alert of alerts) {
    const icon = alert.severity === 'crit' ? '🔴' : alert.severity === 'warn' ? '⚠' : 'ℹ'
    const div = document.createElement('div')
    div.className = `alert-item ${alert.severity}`
    div.setAttribute('role', 'listitem')
    div.innerHTML = `
      <div class="alert-header">
        <span class="alert-title">${icon} ${escHtml(alert.title)}</span>
        <span class="alert-time">${timeAgo(alert.created_at)}</span>
      </div>
      <div class="alert-body">${escHtml(alert.body)}</div>
      <div class="alert-meta">
        <span class="alert-meta-item">HOST: <span>${escHtml(alert.host)}</span></span>
        ${alert.source_ip ? `<span class="alert-meta-item">IP: <span>${escHtml(alert.source_ip)}</span></span>` : ''}
        ${alert.rule_id ? `<span class="alert-meta-item">REGLA: <span>${escHtml(alert.rule_id)}</span></span>` : ''}
      </div>
      <div class="alert-actions">
        <button class="btn-sm green" data-id="${alert.id}" data-action="resolved">RESOLVER</button>
        <button class="btn-sm grey"  data-id="${alert.id}" data-action="reviewing">REVISAR</button>
        <button class="btn-sm red"   data-id="${alert.id}" data-action="ignored">IGNORAR</button>
      </div>
    `
    list.appendChild(div)
  }

  list.querySelectorAll<HTMLButtonElement>('[data-action]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.id!
      const action = btn.dataset.action as 'resolved' | 'reviewing' | 'ignored'
      btn.disabled = true
      try {
        await api.updateAlert(id, action)
        await loadAlerts()
        await loadStats()
      } catch { btn.disabled = false }
    })
  })
}

// ── Agentes ───────────────────────────────────────────────────────────
async function loadAgents() {
  try {
    const agents = await api.agents()
    renderAgentsSidebar(agents)
    renderHeatmap(agents)
    const onlineCount = agents.filter(a => a.status === 'online').length
    setText('#nav-agent-badge', `${onlineCount}/${agents.length}`)
  } catch { /* silencio */ }
}

function renderAgentsSidebar(agents: AgentOut[]) {
  const container = $('#sidebar-agents')
  const label = container.querySelector('.agents-label')!
  container.innerHTML = ''
  container.appendChild(label)
  for (const ag of agents) {
    const statusMap: Record<string, string> = {
      online: 'ok', warn: 'warn', error: 'err', offline: 'off',
    }
    const statusLabel: Record<string, string> = {
      online: 'ONLINE', warn: 'WARN', error: 'ALERTA', offline: 'OFFLINE',
    }
    const row = document.createElement('div')
    row.className = 'agent-row'
    row.innerHTML = `
      <span class="agent-name" title="${escHtml(ag.host)}">${escHtml(ag.name)}</span>
      <span class="agent-status ${statusMap[ag.status] ?? 'off'}">${statusLabel[ag.status] ?? ag.status}</span>
    `
    container.appendChild(row)
  }
}

function renderHeatmap(agents: AgentOut[]) {
  const grid = $('#heatmap')
  grid.innerHTML = ''
  const statusClass: Record<string, string> = {
    online: 'ok', warn: 'warn', error: 'high', offline: 'off',
  }
  for (const ag of agents) {
    const cell = document.createElement('div')
    cell.className = `hm-cell ${statusClass[ag.status] ?? 'off'}`
    cell.setAttribute('role', 'gridcell')
    cell.setAttribute('title', `${ag.name}: ${ag.status.toUpperCase()}`)
    cell.setAttribute('aria-label', `${ag.name} ${ag.status}`)
    cell.innerHTML = `<span class="hm-cell-id">${escHtml(ag.name.slice(0, 7))}</span>`
    grid.appendChild(cell)
  }
}

// ── Eventos / log stream ──────────────────────────────────────────────
async function loadEvents() {
  try {
    const page = await api.events(1, 50)
    for (const ev of [...page.items].reverse()) appendLog(ev, false)
  } catch { /* silencio */ }
}

function appendLog(ev: EventOut, animate = true) {
  const stream = $('#log-stream')
  const line = document.createElement('div')
  const sevClass = ev.severity === 'WARN' ? 'log-warn'
    : ev.severity === 'CRIT' || ev.severity === 'ERROR' ? 'log-crit' : ''
  line.className = `log-line${sevClass ? ' ' + sevClass : ''}${animate ? ' log-new' : ''}`
  const ts = new Date(ev.timestamp).toLocaleTimeString('es', { hour12: false })
  line.innerHTML = `
    <span class="log-ts">${ts} UTC</span>
    <span class="log-sev ${ev.severity}">${ev.severity}</span>
    <span class="log-host">${escHtml(ev.host)}</span>
    <span class="log-msg">${escHtml(ev.message)}</span>
  `
  stream.insertBefore(line, stream.firstChild)
  logTotal++
  setText('#log-count-tag', `${logTotal.toLocaleString()} eventos`)

  // Limit DOM nodes
  while (stream.children.length > 100) stream.removeChild(stream.lastChild!)
}

// ── WebSocket ─────────────────────────────────────────────────────────
function connectWs() {
  wsDisconnect = createWsConnection(token, (msg: WsMessage) => {
    if (msg.type === 'event') {
      appendLog(msg.data, true)
      pushSpark(sparkData.events, logTotal)
      renderSparkline('#spark-events', sparkData.events)
      // Actualizar timeline incrementalmente solo en ventana de 60 min
      if (timelineMinutes === 60) {
        timelineData = pushTimelineEvent(timelineData, msg.data.severity)
        updateTimeline(timelineData)
      }
    }
    if (msg.type === 'alert_update') {
      loadAlerts()
      loadStats()
    }
  })
}

// ── Polling para stats cada 10s ────────────────────────────────────────
function startPolling() {
  setInterval(loadStats, 10_000)
  setInterval(loadAlerts, 15_000)
  setInterval(loadAgents, 20_000)
  setInterval(loadTimeline, 60_000)
}

// ── Sparklines ────────────────────────────────────────────────────────
function pushSpark(arr: number[], val: number) {
  arr.push(val)
  if (arr.length > 20) arr.shift()
}

function renderSparkline(sel: string, data: number[]) {
  const container = $(sel)
  if (!container) return
  container.innerHTML = ''
  const max = Math.max(...data, 1)
  for (let i = 0; i < data.length; i++) {
    const bar = document.createElement('div')
    bar.className = 'spark-bar'
    bar.style.height = Math.max(2, Math.round((data[i] / max) * 100)) + '%'
    container.appendChild(bar)
  }
}

// ── Log Explorer ─────────────────────────────────────────────────────
async function loadExplorer() {
  const tbody = $<HTMLTableSectionElement>('#log-table-body')
  tbody.innerHTML = '<tr class="empty-row"><td colspan="5">Cargando...</td></tr>'

  try {
    const page = await api.events(explorerPage, explorerSize, explorerFilters)
    explorerTotal = page.total
    renderExplorerTable(page.items)
    renderExplorerPagination()
    setText('#log-explorer-total', `${explorerTotal.toLocaleString()} eventos`)
  } catch {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="5">Error al cargar eventos</td></tr>'
  }
}

function renderExplorerTable(items: EventOut[]) {
  const tbody = $<HTMLTableSectionElement>('#log-table-body')
  tbody.innerHTML = ''

  if (!items.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="5">// Sin eventos para los filtros aplicados</td></tr>'
    return
  }

  for (const ev of items) {
    const ts = new Date(ev.timestamp).toLocaleString('es', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
    const tr = document.createElement('tr')
    tr.innerHTML = `
      <td class="col-ts">${escHtml(ts)}</td>
      <td class="sev-${escHtml(ev.severity)}">${escHtml(ev.severity)}</td>
      <td>${escHtml(ev.host)}</td>
      <td class="col-ip">${escHtml(ev.source_ip ?? '—')}</td>
      <td class="col-msg" title="${escHtml(ev.message)}">${escHtml(ev.message)}</td>
    `
    tbody.appendChild(tr)
  }
}

function renderExplorerPagination() {
  const totalPages = Math.max(1, Math.ceil(explorerTotal / explorerSize))
  setText('#page-info', `Página ${explorerPage} / ${totalPages}`)
  $<HTMLButtonElement>('#btn-page-prev').disabled = explorerPage <= 1
  $<HTMLButtonElement>('#btn-page-next').disabled = explorerPage >= totalPages
}

// Filtros
$('#btn-filter-apply').addEventListener('click', () => {
  explorerPage = 1
  explorerFilters = {
    severity: $<HTMLSelectElement>('#filter-severity').value || undefined,
    host: $<HTMLInputElement>('#filter-host').value.trim() || undefined,
    date_from: $<HTMLInputElement>('#filter-date-from').value
      ? new Date($<HTMLInputElement>('#filter-date-from').value).toISOString() : undefined,
    date_to: $<HTMLInputElement>('#filter-date-to').value
      ? new Date($<HTMLInputElement>('#filter-date-to').value).toISOString() : undefined,
  }
  loadExplorer()
})

$('#btn-filter-reset').addEventListener('click', () => {
  explorerPage = 1
  explorerFilters = {}
  $<HTMLSelectElement>('#filter-severity').value = ''
  $<HTMLInputElement>('#filter-host').value = ''
  $<HTMLInputElement>('#filter-date-from').value = ''
  $<HTMLInputElement>('#filter-date-to').value = ''
  loadExplorer()
})

$('#btn-page-prev').addEventListener('click', () => {
  if (explorerPage > 1) { explorerPage--; loadExplorer() }
})

$('#btn-page-next').addEventListener('click', () => {
  if (explorerPage < Math.ceil(explorerTotal / explorerSize)) { explorerPage++; loadExplorer() }
})

// ── XSS: escapar HTML ────────────────────────────────────────────────
function escHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
