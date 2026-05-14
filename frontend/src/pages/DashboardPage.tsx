import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Ticket, CheckCircle, Clock, AlertCircle, Plus, ArrowRight, Zap } from 'lucide-react'
import { DashboardSkeleton } from '@/components/ui/loading'

const statusColor: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  open: 'destructive',
  in_progress: 'secondary',
  resolved: 'default',
  closed: 'outline',
}

const priorityColor: Record<string, string> = {
  high: 'text-red-500',
  medium: 'text-yellow-500',
  low: 'text-green-500',
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [tickets, setTickets] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/ticket?limit=20').then((r) => {
      setTickets(r.data.items ?? [])
      setTotal(r.data.total ?? 0)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <DashboardSkeleton />
  const open = tickets.filter((t) => t.status === 'open').length
  const inProgress = tickets.filter((t) => t.status === 'in_progress').length
  const resolved = tickets.filter((t) => t.status === 'resolved').length
  const highPriority = tickets.filter((t) => t.priority === 'high').length
  const recent = tickets.slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Good {getGreeting()}, {user?.full_name.split(' ')[0]} 👋
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Here's an overview of your support tickets
          </p>
        </div>
        <Link to="/tickets/new">
          <Button className="gap-2">
            <Plus size={16} /> New Ticket
          </Button>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total Tickets', value: total, icon: Ticket, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-950' },
          { label: 'Open', value: open, icon: AlertCircle, color: 'text-red-500', bg: 'bg-red-50 dark:bg-red-950' },
          { label: 'In Progress', value: inProgress, icon: Clock, color: 'text-yellow-500', bg: 'bg-yellow-50 dark:bg-yellow-950' },
          { label: 'Resolved', value: resolved, icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-950' },
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <Card key={label} className="hover:shadow-md transition-shadow">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
                <div className={`p-1.5 rounded-md ${bg}`}>
                  <Icon size={14} className={color} />
                </div>
              </div>
              <p className="text-3xl font-bold tracking-tight">{loading ? '—' : value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* High priority alert */}
      {highPriority > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
          <Zap size={16} className="text-red-500 shrink-0" />
          <p className="text-sm text-red-700 dark:text-red-300">
            You have <strong>{highPriority}</strong> high priority {highPriority === 1 ? 'ticket' : 'tickets'} that need attention.
          </p>
          <Link to="/tickets" className="ml-auto shrink-0">
            <Button variant="destructive" size="sm">View</Button>
          </Link>
        </div>
      )}

      {/* Recent tickets */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle className="text-base">Recent Tickets</CardTitle>
          <Link to="/tickets">
            <Button variant="ghost" size="sm" className="gap-1 text-muted-foreground">
              View all <ArrowRight size={14} />
            </Button>
          </Link>
        </CardHeader>
        <CardContent className="p-0">
          {recent.length === 0 ? (
            <div className="text-center py-12">
              <Ticket size={32} className="mx-auto text-muted-foreground/40 mb-3" />
              <p className="text-sm text-muted-foreground">No tickets yet</p>
              <Link to="/tickets/new">
                <Button variant="outline" size="sm" className="mt-3 gap-2">
                  <Plus size={14} /> Create your first ticket
                </Button>
              </Link>
            </div>
          ) : (
            <div className="divide-y">
              {recent.map((t) => (
                <Link
                  key={t.id}
                  to={`/tickets/${t.id}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors group"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                      {t.message?.slice(0, 90)}{t.message?.length > 90 ? '…' : ''}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">
                        {new Date(t.created_at).toLocaleDateString()}
                      </span>
                      {t.priority && (
                        <span className={`text-xs font-medium capitalize ${priorityColor[t.priority]}`}>
                          · {t.priority}
                        </span>
                      )}
                      {t.category && (
                        <span className="text-xs text-muted-foreground capitalize">· {t.category}</span>
                      )}
                    </div>
                  </div>
                  <Badge variant={statusColor[t.status] ?? 'outline'} className="capitalize shrink-0 text-xs">
                    {t.status.replace('_', ' ')}
                  </Badge>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function getGreeting() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}
