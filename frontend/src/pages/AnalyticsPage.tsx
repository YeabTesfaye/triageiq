import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import { BarChart2, Ticket, Bot, TrendingUp } from 'lucide-react'

interface Analytics {
  total_tickets: number
  ai_processing: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  by_priority: Record<string, number>
  scope: string
}

const STATUS_COLORS: Record<string, string> = {
  open: '#ef4444',
  in_progress: '#f59e0b',
  resolved: '#22c55e',
  closed: '#94a3b8',
}

const CATEGORY_COLORS: Record<string, string> = {
  billing: '#8b5cf6',
  technical: '#3b82f6',
  general: '#06b6d4',
}

const PRIORITY_COLORS: Record<string, string> = {
  high: '#ef4444',
  medium: '#f59e0b',
  low: '#22c55e',
}

const RADIAN = Math.PI / 180
const renderCustomLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }: any) => {
  if (percent < 0.05) return null
  const r = innerRadius + (outerRadius - innerRadius) * 0.5
  const x = cx + r * Math.cos(-midAngle * RADIAN)
  const y = cy + r * Math.sin(-midAngle * RADIAN)
  return (
    <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize={12} fontWeight={600}>
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  )
}

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/analytics').then((r) => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <AnalyticsSkeleton />
  if (!data) return null

  const aiResolved = data.total_tickets - data.ai_processing
  const aiRate = data.total_tickets > 0 ? Math.round((aiResolved / data.total_tickets) * 100) : 0

  const statusData = Object.entries(data.by_status).map(([name, value]) => ({ name, value }))
  const categoryData = Object.entries(data.by_category).map(([name, value]) => ({ name, value }))
  const priorityData = Object.entries(data.by_priority).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    value,
    fill: PRIORITY_COLORS[name] ?? '#94a3b8',
  }))

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <BarChart2 size={22} /> Analytics
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data.scope === 'global' ? 'Global stats across all users' : 'Your personal ticket stats'}
          </p>
        </div>
        <Badge variant="outline" className="capitalize">{data.scope}</Badge>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: 'Total Tickets',
            value: data.total_tickets,
            icon: Ticket,
            color: 'text-blue-500',
            bg: 'bg-blue-50 dark:bg-blue-950',
            sub: 'All time',
          },
          {
            label: 'AI Processed',
            value: aiResolved,
            icon: Bot,
            color: 'text-purple-500',
            bg: 'bg-purple-50 dark:bg-purple-950',
            sub: `${aiRate}% of total`,
          },
          {
            label: 'Pending AI',
            value: data.ai_processing,
            icon: TrendingUp,
            color: 'text-yellow-500',
            bg: 'bg-yellow-50 dark:bg-yellow-950',
            sub: 'Awaiting analysis',
          },
          {
            label: 'Resolved',
            value: data.by_status['resolved'] ?? 0,
            icon: Ticket,
            color: 'text-green-500',
            bg: 'bg-green-50 dark:bg-green-950',
            sub: `${data.total_tickets > 0 ? Math.round(((data.by_status['resolved'] ?? 0) / data.total_tickets) * 100) : 0}% resolution rate`,
          },
        ].map(({ label, value, icon: Icon, color, bg, sub }) => (
          <Card key={label} className="hover:shadow-md transition-shadow">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
                <div className={`p-1.5 rounded-md ${bg}`}>
                  <Icon size={14} className={color} />
                </div>
              </div>
              <p className="text-3xl font-bold tracking-tight">{value}</p>
              <p className="text-xs text-muted-foreground mt-1">{sub}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts row 1 */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Status bar chart */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Tickets by Status</CardTitle>
            <CardDescription>Distribution across all statuses</CardDescription>
          </CardHeader>
          <CardContent>
            {statusData.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={statusData} barSize={36}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} tickFormatter={(v) => v.replace('_', ' ')} />
                  <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    formatter={(v: number) => [v, 'Tickets']}
                    labelFormatter={(l) => l.replace('_', ' ')}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {statusData.map((entry) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[entry.name] ?? '#94a3b8'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Priority bar chart */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Tickets by Priority</CardTitle>
            <CardDescription>AI-assigned priority breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            {priorityData.length === 0 ? (
              <EmptyChart />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={priorityData} barSize={48}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    formatter={(v: number) => [v, 'Tickets']}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {priorityData.map((entry) => (
                      <Cell key={entry.name} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Category pie chart */}
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
                    {categoryData.map((entry) => (
                      <Cell key={entry.name} fill={CATEGORY_COLORS[entry.name] ?? '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ fontSize: 12, borderRadius: 8 }}
                    formatter={(v: number) => [v, 'Tickets']}
                  />
                  <Legend
                    formatter={(value) => value.charAt(0).toUpperCase() + value.slice(1)}
                    iconType="circle"
                    iconSize={10}
                  />
                </PieChart>
              </ResponsiveContainer>

              {/* Category breakdown list */}
              <div className="w-full sm:w-48 shrink-0 space-y-2">
                {categoryData.map(({ name, value }) => (
                  <div key={name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2.5 w-2.5 rounded-full shrink-0"
                        style={{ background: CATEGORY_COLORS[name] ?? '#94a3b8' }}
                      />
                      <span className="text-sm capitalize">{name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{value}</span>
                      <span className="text-xs text-muted-foreground">
                        {data.total_tickets > 0 ? Math.round((value / data.total_tickets) * 100) : 0}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function EmptyChart() {
  return (
    <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">
      No data yet
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
        <Skeleton className="h-6 w-16 rounded-full" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-7 w-7 rounded-md" />
              </div>
              <Skeleton className="h-9 w-12" />
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
              <Skeleton className="h-[220px] w-full rounded-lg" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-5 w-36" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[240px] w-full rounded-lg" />
        </CardContent>
      </Card>
    </div>
  )
}
