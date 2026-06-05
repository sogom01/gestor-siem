import * as d3 from 'd3'
import type { TimelineBucket } from '../api/types'

type SevKey = 'INFO' | 'WARN' | 'ERROR' | 'CRIT'

const SEV_KEYS: SevKey[] = ['INFO', 'WARN', 'ERROR', 'CRIT']
const SEV_COLOR: Record<SevKey, string> = {
  INFO:  '#00CC66',
  WARN:  '#FFAA00',
  ERROR: '#FF3B3B',
  CRIT:  '#FF0000',
}

interface ChartState {
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>
  xScale: d3.ScaleBand<string>
  yScale: d3.ScaleLinear<number, number>
  xAxis: d3.Selection<SVGGElement, unknown, null, undefined>
  yAxis: d3.Selection<SVGGElement, unknown, null, undefined>
  plotArea: d3.Selection<SVGGElement, unknown, null, undefined>
  width: number
  height: number
}

let state: ChartState | null = null

export function initTimeline(container: HTMLElement): void {
  container.innerHTML = ''

  const margin = { top: 12, right: 16, bottom: 36, left: 38 }
  const width  = container.clientWidth  - margin.left - margin.right
  const height = container.clientHeight - margin.top  - margin.bottom

  const svg = d3.select(container)
    .append('svg')
    .attr('width',  '100%')
    .attr('height', '100%')
    .attr('aria-label', 'Timeline de eventos')
    .style('font-family', "'Share Tech Mono', monospace")

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`)

  const xScale = d3.scaleBand<string>().range([0, width]).padding(0.15)
  const yScale = d3.scaleLinear().range([height, 0])

  const xAxis = g.append('g')
    .attr('class', 'x-axis')
    .attr('transform', `translate(0,${height})`)

  const yAxis = g.append('g').attr('class', 'y-axis')

  const plotArea = g.append('g').attr('class', 'plot-area')

  // Leyenda
  const legend = svg.append('g')
    .attr('transform', `translate(${margin.left + width - 180},${margin.top})`)

  SEV_KEYS.forEach((k, i) => {
    const row = legend.append('g').attr('transform', `translate(${i * 46},0)`)
    row.append('rect').attr('width', 8).attr('height', 8).attr('y', -1).attr('fill', SEV_COLOR[k])
    row.append('text')
      .attr('x', 11).attr('y', 8)
      .attr('fill', '#5A8068')
      .attr('font-size', '9px')
      .text(k)
  })

  state = { svg, xScale, yScale, xAxis, yAxis, plotArea, width, height }
}

export function updateTimeline(data: TimelineBucket[]): void {
  if (!state || !data.length) return
  const { xScale, yScale, xAxis, yAxis, plotArea, width, height } = state

  const keys = d3.stack<TimelineBucket, SevKey>()
    .keys(SEV_KEYS)
    .value((d, k) => d[k])(data)

  const maxVal = d3.max(keys[keys.length - 1], d => d[1]) ?? 1
  const labels = data.map(d => String(d.ts))

  xScale.domain(labels).range([0, width])
  yScale.domain([0, Math.ceil(maxVal * 1.1) || 1]).range([height, 0]).nice()

  // Mostrar solo ~8 ticks en X
  const step = Math.max(1, Math.floor(data.length / 8))
  const tickValues = labels.filter((_, i) => i % step === 0)

  xAxis.transition().duration(300).call(
    d3.axisBottom(xScale)
      .tickValues(tickValues)
      .tickFormat(v => {
        const d = new Date(Number(v) * 1000)
        return `${String(d.getUTCHours()).padStart(2,'0')}:${String(d.getUTCMinutes()).padStart(2,'0')}`
      })
  )
  styleAxis(xAxis)

  yAxis.transition().duration(300).call(
    d3.axisLeft(yScale).ticks(4).tickFormat(d3.format('d'))
  )
  styleAxis(yAxis)

  // Barras apiladas
  const groups = plotArea.selectAll<SVGGElement, d3.Series<TimelineBucket, SevKey>>('.sev-group')
    .data(keys, d => d.key)

  groups.enter()
    .append('g')
    .attr('class', 'sev-group')
    .attr('fill', d => SEV_COLOR[d.key as SevKey])
    .merge(groups)
    .selectAll<SVGRectElement, d3.SeriesPoint<TimelineBucket>>('rect')
    .data(d => d, d => String(d.data.ts))
    .join(
      enter => enter.append('rect')
        .attr('x', d => xScale(String(d.data.ts)) ?? 0)
        .attr('y', height)
        .attr('width', xScale.bandwidth())
        .attr('height', 0)
        .call(sel => sel.transition().duration(300)
          .attr('y', d => yScale(d[1]))
          .attr('height', d => Math.max(0, yScale(d[0]) - yScale(d[1])))),
      update => update.call(sel => sel.transition().duration(300)
        .attr('x', d => xScale(String(d.data.ts)) ?? 0)
        .attr('y', d => yScale(d[1]))
        .attr('width', xScale.bandwidth())
        .attr('height', d => Math.max(0, yScale(d[0]) - yScale(d[1])))),
      exit => exit.transition().duration(200).attr('height', 0).attr('y', height).remove()
    )

  groups.exit().remove()
}

function styleAxis(g: d3.Selection<SVGGElement, unknown, null, undefined>) {
  g.selectAll('line, path').attr('stroke', 'rgba(0,255,128,.1)')
  g.selectAll('text')
    .attr('fill', '#5A8068')
    .attr('font-size', '9px')
    .attr('font-family', "'Share Tech Mono', monospace")
}

// Actualiza el bucket del último minuto sin refetch completo
export function pushTimelineEvent(data: TimelineBucket[], severity: string): TimelineBucket[] {
  const nowKey = Math.floor(Date.now() / 60000) * 60
  const last = data[data.length - 1]
  if (last && last.ts === nowKey) {
    const sev = severity as SevKey
    if (sev in last) last[sev]++
  } else {
    const bucket: TimelineBucket = { ts: nowKey, INFO: 0, WARN: 0, ERROR: 0, CRIT: 0 }
    const sev = severity as SevKey
    if (sev in bucket) bucket[sev]++
    data.push(bucket)
    if (data.length > 60) data.shift()
  }
  return data
}
