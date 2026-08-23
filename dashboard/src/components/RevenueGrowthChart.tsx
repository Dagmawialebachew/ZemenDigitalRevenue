import { useMemo, useState, type PointerEvent } from 'react'
import type { TrendPoint } from '../api/types'
import { money } from './UI'

export type OverviewRange = 7 | 14 | 30 | 90

const RANGES: OverviewRange[] = [7, 14, 30, 90]
const WIDTH = 820
const HEIGHT = 286
const LEFT = 58
const RIGHT = 50
const TOP = 20
const BOTTOM = 34
const PLOT_WIDTH = WIDTH - LEFT - RIGHT
const PLOT_HEIGHT = HEIGHT - TOP - BOTTOM

function dateLabel(value: string, compact = false) {
  const date = new Date(`${value.slice(0, 10)}T12:00:00`)
  return date.toLocaleDateString([], compact
    ? { month: 'short', day: 'numeric' }
    : { weekday: 'short', month: 'short', day: 'numeric' })
}

function compactNumber(value: number) {
  return Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

function axisMaximum(values: number[]) {
  const maximum = Math.max(...values, 0)
  if (maximum <= 0) return 1
  const magnitude = 10 ** Math.floor(Math.log10(maximum))
  return Math.ceil(maximum / magnitude) * magnitude
}

export function RevenueGrowthChart({
  points,
  range,
  loading,
  error,
  onRange,
}: {
  points: TrendPoint[]
  range: OverviewRange
  loading: boolean
  error?: string
  onRange: (range: OverviewRange) => void
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [showRevenue, setShowRevenue] = useState(true)
  const [showUsers, setShowUsers] = useState(true)

  const chart = useMemo(() => {
    const revenues = points.map(point => Number(point.revenue || 0))
    const users = points.map(point => Number(point.users || 0))
    const revenueMax = axisMaximum(revenues)
    const usersMax = axisMaximum(users)
    const x = (index: number) => LEFT + (index + 0.5) * PLOT_WIDTH / Math.max(points.length, 1)
    const revenueY = (value: number) => TOP + PLOT_HEIGHT - value / revenueMax * PLOT_HEIGHT
    const usersY = (value: number) => TOP + PLOT_HEIGHT - value / usersMax * PLOT_HEIGHT
    const userPath = users.map((value, index) => `${index ? 'L' : 'M'} ${x(index)} ${usersY(value)}`).join(' ')
    return {
      revenues,
      users,
      revenueMax,
      usersMax,
      x,
      revenueY,
      usersY,
      userPath,
      revenueTotal: revenues.reduce((sum, value) => sum + value, 0),
      userTotal: users.reduce((sum, value) => sum + value, 0),
    }
  }, [points])

  const selected = activeIndex === null ? null : points[activeIndex]
  const selectedX = activeIndex === null ? 0 : chart.x(activeIndex)
  const selectedY = activeIndex === null
    ? TOP
    : Math.min(chart.revenueY(chart.revenues[activeIndex]), chart.usersY(chart.users[activeIndex]))
  const barWidth = Math.max(3, Math.min(22, PLOT_WIDTH / Math.max(points.length, 1) * .58))
  const labelStep = range <= 14 ? 2 : range <= 30 ? 5 : 15

  const inspect = (event: PointerEvent<SVGRectElement>) => {
    if (!points.length) return
    const bounds = event.currentTarget.getBoundingClientRect()
    const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width))
    setActiveIndex(Math.min(points.length - 1, Math.floor(ratio * points.length)))
  }

  const moveSelection = (direction: number) => {
    if (!points.length) return
    setActiveIndex(current => Math.max(0, Math.min(points.length - 1, (current ?? points.length - 1) + direction)))
  }

  return <div className={`growth-chart${loading ? ' growth-chart--loading' : ''}`}>
    <div className="growth-chart__toolbar">
      <div className="growth-chart__totals">
        <div><span>Paid revenue</span><strong>{money(chart.revenueTotal)}</strong></div>
        <div><span>New users</span><strong>{chart.userTotal.toLocaleString()}</strong></div>
      </div>
      <div className="range-switcher" aria-label="Chart date range">
        {RANGES.map(option => <button className={option === range ? 'active' : ''} disabled={loading} key={option} onClick={() => onRange(option)}>{option}D</button>)}
      </div>
    </div>
    <div className="growth-chart__legend">
      <button aria-pressed={showRevenue} className={showRevenue ? 'active' : ''} onClick={() => setShowRevenue(value => !value)}><i className="legend-bar"/>Revenue</button>
      <button aria-pressed={showUsers} className={showUsers ? 'active' : ''} onClick={() => setShowUsers(value => !value)}><i className="legend-line"/>New users</button>
      <span>Addis Ababa time</span>
    </div>
    <div
      className="growth-chart__canvas"
      tabIndex={0}
      role="img"
      aria-label={`${range} day chart of paid revenue and new users`}
      onKeyDown={event => {
        if (event.key === 'ArrowLeft') { event.preventDefault(); moveSelection(-1) }
        if (event.key === 'ArrowRight') { event.preventDefault(); moveSelection(1) }
        if (event.key === 'Escape') setActiveIndex(null)
      }}
    >
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="overviewRevenue" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#a7ee5d"/><stop offset="1" stopColor="#4f8f21" stopOpacity=".24"/></linearGradient>
          <linearGradient id="overviewUsers" x1="0" y1="0" x2="1" y2="0"><stop stopColor="#f3f0e7"/><stop offset="1" stopColor="#8bdf31"/></linearGradient>
          <filter id="overviewGlow"><feGaussianBlur stdDeviation="3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        {[0, .25, .5, .75, 1].map(ratio => {
          const y = TOP + PLOT_HEIGHT * (1 - ratio)
          return <g key={ratio}><line className="chart-gridline" x1={LEFT} x2={WIDTH - RIGHT} y1={y} y2={y}/><text className="chart-axis chart-axis--left" x={LEFT - 9} y={y + 3}>{compactNumber(chart.revenueMax * ratio)}</text><text className="chart-axis chart-axis--right" x={WIDTH - RIGHT + 9} y={y + 3}>{compactNumber(chart.usersMax * ratio)}</text></g>
        })}
        {showRevenue && points.map((point, index) => {
          const y = chart.revenueY(chart.revenues[index])
          return <rect className="revenue-bar" key={point.day} x={chart.x(index) - barWidth / 2} y={y} width={barWidth} height={Math.max(1, TOP + PLOT_HEIGHT - y)} rx={Math.min(5, barWidth / 3)}/>
        })}
        {showUsers && <><path className="users-line users-line--glow" d={chart.userPath}/><path className="users-line" d={chart.userPath}/>{points.map((point, index) => <circle className="users-point" key={point.day} cx={chart.x(index)} cy={chart.usersY(chart.users[index])} r={activeIndex === index ? 4.5 : range <= 14 ? 2.5 : 1.6}/>)}</>}
        {points.map((point, index) => (index % labelStep === 0 || index === points.length - 1) && <text className="chart-date" x={chart.x(index)} y={HEIGHT - 8} key={point.day}>{dateLabel(point.day, true)}</text>)}
        {activeIndex !== null && <line className="chart-crosshair" x1={selectedX} x2={selectedX} y1={TOP} y2={TOP + PLOT_HEIGHT}/>} 
        <rect className="chart-hitarea" x={LEFT} y={TOP} width={PLOT_WIDTH} height={PLOT_HEIGHT} onPointerMove={inspect} onPointerDown={inspect} onPointerLeave={() => setActiveIndex(null)}/>
      </svg>
      {selected && <div className={`chart-tooltip${selectedX > WIDTH * .72 ? ' chart-tooltip--left' : ''}`} style={{left:`${selectedX / WIDTH * 100}%`,top:`${Math.max(4, selectedY / HEIGHT * 100 - 5)}%`}}><span>{dateLabel(selected.day)}</span><div><i className="legend-bar"/><b>Revenue</b><strong>{money(selected.revenue)}</strong></div><div><i className="legend-line"/><b>New users</b><strong>{selected.users.toLocaleString()}</strong></div></div>}
      {loading && <div className="chart-loading" aria-label="Loading chart"><i/><i/><i/></div>}
      {error && !loading && <div className="chart-error">{error}</div>}
    </div>
  </div>
}
