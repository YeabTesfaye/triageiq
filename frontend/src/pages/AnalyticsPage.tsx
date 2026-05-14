import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts'
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent'
import { BarChart2, Bot, Clock, Tag, TrendingUp, Ticket, Users } from 'lucide-react'

// ─── Types ────────────────────────────────────────────────────────────────────
interface Analytics {
  total_tickets: number
  ai_processing: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  by_priority: Record<string, number>
  scope: 'user' | 'global'
  avg_resolution_hours?: number
  most_common_category?: string
  peak_day?: string
}

type TimeRange = '7d' | '30d' | '90d' | 'all'

// ─── Constants ────────────────────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  open:        '#ef4444',
  in_progress: '#f59e0b',
  resolved:    '#22c55e',
  closed:      '#94a3b8',
}

const PRIORITY_COLORS: Record<string, string> = {
  high:   '#ef4444',
  medium: '#f59e0b',
  low:    '#22c55e',
}

const CATEGORY_COLORS = [
  '#8b5cf6', '#3b82f6', '#06b6d4', '#f97316', '#ec4899', '#14b8a6',
]

const ALL_STATUSES   = ['open', 'in_progress', 'resolved', 'closed']
const ALL_PRIORITIES = ['high', 'medium', 'low']

const TIME_RANGE_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '7d',  label: '7D'  },
  { value: '30d', label: '30D' },
  { value: '90d', label: '90D' },
  { value: 'all', label: 'All' },
]

const RADIAN = Math.PI / 180

// ─── Custom tooltip ───────────────────────────────────────────────────────────
interface TooltipEntry {
  name?: NameType
  value?: ValueType
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipEntry[]
  label?: string | number
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-popover text-popover-foreground shadow-md px-3 py-2 text-xs">
      <p className="font-semibold mb-1 capitalize">
        {String(label ?? '').replace('_', ' ')}
      </p>
      {payload.map((p, i) => (
        <p key={i} className="text-muted-foreground">
          {p.value} ticket{p.value !== 1 ? 's' : ''}
        </p>
      ))}
    </div>
  )
}

// ─── Pie label ────────────────────────────────────────────────────────────────
// recharts types every PieLabelRenderProps field as `number | undefined`,
// so all params must be optional and guarded before arithmetic.
function renderCustomLabel({
  cx,
  cy,
  midAngle,
  innerRadius,
  outerRadius,
  percent,
}: {
  cx?: number
  cy?: number
  midAngle?: number
  innerRadius?: number
  outerRadius?: number
  percent?: number
}) {
  if (
    cx === undefined ||
    cy === undefined ||
    midAngle === undefined ||
    innerRadius === undefined ||
    outerRadius === undefined ||
    percent === undefined ||
    percent < 0.06
  ) {
    return null
  }
  const r = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text
      x={x}
      y={y}
      fill="white"
      textAnchor="middle"
      dominantBaseline="central"
      fontSize={11}
      fontWeight={700}
    >
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function AnalyticsPage() {
  const [data, setData]           = useState<Analytics | null>(null)
  const [timeRange, setTimeRange] = useState<TimeRange>('30d')
  const [scope, setScope]         = useState<'user' | 'global'>('user')

  // Two plain state counters — no ref, so safe to read during render.
  // fetchCount increments when a fetch starts; settledCount catches up when it
  // finishes. loading = the two are out of sync.
  // We use the functional updater form of setFetchCount so we can capture the
  // new ID synchronously inside the effect without touching state mid-render.
  const [fetchCount,   setFetchCount]   = useState(0)
  const [settledCount, setSettledCount] = useState(0)
  const loading = fetchCount !== settledCount

  useEffect(() => {
    let cancelled = false

    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFetchCount((prev) => prev + 1)

    api
      .get<Analytics>('/analytics', { params: { range: timeRange, scope } })
      .then((r) => {
        if (!cancelled) setData(r.data)
      })
      .finally(() => {
        if (!cancelled) setSettledCount((prev) => prev + 1)
      })

    return () => { cancelled = true }
  }, [timeRange, scope])

  if (loading) return <AnalyticsSkeleton />
  if (!data)   return null

  // ── Derived values ──────────────────────────────────────────────────────────
  const aiResolved     = data.total_tickets - data.ai_processing
  const aiRate         = data.total_tickets > 0
    ? Math.round((aiResolved / data.total_tickets) * 100)
    : 0
  const resolvedCount  = data.by_status['resolved'] ?? 0
  const resolutionRate = data.total_tickets > 0
    ? Math.round((resolvedCount / data.total_tickets) * 100)
    : 0

  const statusData = ALL_STATUSES.map((s) => ({
    name:  s,
    value: data.by_status[s] ?? 0,
  }))

  const priorityData = ALL_PRIORITIES.map((p) => ({
    name:  p.charAt(0).toUpperCase() + p.slice(1),
    key:   p,
    value: data.by_priority[p] ?? 0,
  }))

  const categoryData = Object.entries(data.by_category).map(([name, value]) => ({
    name,
    value,
  }))

  const mostCommonCategory =
    data.most_common_category ??
    (categoryData.slice().sort((a, b) => b.value - a.value)[0]?.name ?? '—')

  return (
    <div className="space-y-6">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <BarChart2 size={22} /> Analytics
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {scope === 'global' ? 'Stats across all users' : 'Your personal ticket stats'}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Time range pill selector */}
          <div className="flex items-center gap-1 rounded-lg border bg-muted/40 p-1">
            {TIME_RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTimeRange(opt.value)}
                className={[
                  'px-3 py-1 rounded-md text-xs font-medium transition-all',
                  timeRange === opt.value
                    ? 'bg-background shadow-sm text-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                ].join(' ')}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Scope toggle — clearly labeled so users know what it switches */}
          <div className="flex items-center gap-1 rounded-lg border bg-muted/40 p-1">
            <button
              onClick={() => setScope('user')}
              className={[
                'flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all',
                scope === 'user'
                  ? 'bg-background shadow-sm text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              ].join(' ')}
            >
              <Ticket size={11} />
              My tickets
            </button>
            <button
              onClick={() => setScope('global')}
              className={[
                'flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all',
                scope === 'global'
                  ? 'bg-background shadow-sm text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              ].join(' ')}
            >
              <Users size={11} />
              All tickets
            </button>
          </div>
        </div>
      </div>

      {/* ── KPI cards ───────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(
          [
            {
              label: 'AI Processed',
              value: `${aiRate}%`,
              icon:  Bot,
              color: 'text-purple-500',
              bg:    'bg-purple-50 dark:bg-purple-950',
              sub:   `${aiResolved} of ${data.total_tickets} tickets`,
              small: false,
            },
            {
              label: 'Resolution Rate',
              value: `${resolutionRate}%`,
              icon:  TrendingUp,
              color: 'text-green-500',
              bg:    'bg-green-50 dark:bg-green-950',
              sub:   `${resolvedCount} resolved`,
              small: false,
            },
            {
              label: 'Avg. Resolution',
              value: data.avg_resolution_hours != null ? `${data.avg_resolution_hours}h` : '—',
              icon:  Clock,
              color: 'text-blue-500',
              bg:    'bg-blue-50 dark:bg-blue-950',
              sub:   'From open to resolved',
              small: false,
            },
            {
              label: 'Top Category',
              value: mostCommonCategory,
              icon:  Tag,
              color: 'text-orange-500',
              bg:    'bg-orange-50 dark:bg-orange-950',
              sub:   'Most submitted type',
              small: true,
            },
          ] as const
        ).map(({ label, value, icon: Icon, color, bg, sub, small }) => (
          <Card key={label} className="hover:shadow-md transition-shadow">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {label}
                </span>
                <div className={`p-1.5 rounded-md ${bg}`}>
                  <Icon size={14} className={color} />
                </div>
              </div>
              <p className={`font-bold tracking-tight capitalize ${small ? 'text-xl' : 'text-3xl'}`}>
                {value}
              </p>
              <p className="text-xs text-muted-foreground mt-1">{sub}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Bar charts ──────────────────────────────────────────────────────── */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Tickets by Status</CardTitle>
            <CardDescription>Distribution across all statuses</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={statusData} barSize={32} style={{ background: 'transparent' }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="currentColor"
                  strokeOpacity={0.08}
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v: string) => v.replace('_', ' ')}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  width={24}
                />
                <Tooltip
                  content={<CustomTooltip />}
                  cursor={{ fill: 'currentColor', fillOpacity: 0.04 }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {statusData.map((entry) => (
                    <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Tickets by Priority</CardTitle>
            <CardDescription>AI-assigned priority breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={priorityData} barSize={48} style={{ background: 'transparent' }}>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="currentColor"
                  strokeOpacity={0.08}
                  vertical={false}
                />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  allowDecimals={false}
                  axisLine={false}
                  tickLine={false}
                  width={24}
                />
                <Tooltip
                  content={<CustomTooltip />}
                  cursor={{ fill: 'currentColor', fillOpacity: 0.04 }}
                />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {priorityData.map((entry) => (
                    <Cell key={entry.key} fill={PRIORITY_COLORS[entry.key] ?? '#94a3b8'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* ── Category pie chart ───────────────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Tickets by Category</CardTitle>
          <CardDescription>AI-classified category distribution</CardDescription>
        </CardHeader>
        <CardContent>
          {categoryData.length === 0 ? (
            <EmptyChart />
          ) : (
            <div className="flex flex-col sm:flex-row items-center gap-6">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    dataKey="value"
                    labelLine={false}
                    label={renderCustomLabel}
                  >
                    {categoryData.map((entry, i) => (
                      <Cell
                        key={entry.name}
                        fill={CATEGORY_COLORS[i % CATEGORY_COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    formatter={(value) =>
                      (value as string).charAt(0).toUpperCase() + (value as string).slice(1)
                    }
                    iconType="circle"
                    iconSize={8}
                    wrapperStyle={{ fontSize: 12 }}
                  />
                </PieChart>
              </ResponsiveContainer>

              <div className="w-full sm:w-52 shrink-0 space-y-2.5">
                {categoryData
                  .slice()
                  .sort((a, b) => b.value - a.value)
                  .map(({ name, value }, i) => {
                    const pct =
                      data.total_tickets > 0
                        ? Math.round((value / data.total_tickets) * 100)
                        : 0
                    return (
                      <div key={name} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <div
                              className="h-2 w-2 rounded-full shrink-0"
                              style={{ background: CATEGORY_COLORS[i % CATEGORY_COLORS.length] }}
                            />
                            <span className="capitalize">{name}</span>
                          </div>
                          <span className="font-medium tabular-nums">{value}</span>
                        </div>
                        <div className="h-1 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width:      `${pct}%`,
                              background: CATEGORY_COLORS[i % CATEGORY_COLORS.length],
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ─── Supporting components ────────────────────────────────────────────────────
function EmptyChart() {
  return (
    <div className="h-55 flex items-center justify-center text-sm text-muted-foreground">
      No data for this period
    </div>
  )
}

function AnalyticsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <Skeleton className="h-7 w-36" />
          <Skeleton className="h-4 w-48" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-8 w-36 rounded-lg" />
          <Skeleton className="h-8 w-40 rounded-lg" />
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-7 w-7 rounded-md" />
              </div>
              <Skeleton className="h-9 w-16" />
              <Skeleton className="h-3 w-24 mt-1" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid md:grid-cols-2 gap-4">
        {[...Array(2)].map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-5 w-36" />
              <Skeleton className="h-3 w-48" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-55 w-full rounded-lg" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-36" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-60 w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  )
}
