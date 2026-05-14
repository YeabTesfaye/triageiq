import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Plus, ChevronRight, Ticket, Zap, Tag, Search } from 'lucide-react'
import { TicketsListSkeleton } from '@/components/ui/loading'
import { Input } from '@/components/ui/input'

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

export default function TicketsPage() {
  const [tickets, setTickets] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const limit = 10

  useEffect(() => {
    setLoading(true)
    api.get(`/ticket?limit=${limit}&offset=${offset}`).then((r) => {
      setTickets(r.data.items ?? [])
      setTotal(r.data.total ?? 0)
    }).finally(() => setLoading(false))
  }, [offset])

  const filtered = (statusFilter === 'all' ? tickets : tickets.filter((t) => t.status === statusFilter))
    .filter((t) => !search || t.message?.toLowerCase().includes(search.toLowerCase()))

  if (loading) return <TicketsListSkeleton />

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tickets</h1>
          <p className="text-sm text-muted-foreground mt-1">{total} total tickets</p>
        </div>
        <Link to="/tickets/new">
          <Button className="gap-2"><Plus size={16} /> New Ticket</Button>
        </Link>
      </div>

      {/* Filter + Search */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tickets…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-8 text-sm"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setOffset(0) }}>
          <SelectTrigger className="w-36 h-8 text-sm">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
            <SelectItem value="closed">Closed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* List */}
      <Card>
        <CardContent className="p-0">
          {filtered.length === 0 ? (
            <div className="text-center py-16">
              <Ticket size={36} className="mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground">No tickets found</p>
              <Link to="/tickets/new">
                <Button variant="outline" size="sm" className="mt-3 gap-2">
                  <Plus size={14} /> Create one
                </Button>
              </Link>
            </div>
          ) : (
            <div className="divide-y">
              {filtered.map((t) => (
                <Link
                  key={t.id}
                  to={`/tickets/${t.id}`}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-muted/50 transition-colors group"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                      {t.message?.slice(0, 100)}{t.message?.length > 100 ? '…' : ''}
                    </p>
                    <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                      <span className="text-xs text-muted-foreground">
                        {new Date(t.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                      {t.priority && (
                        <span className={`flex items-center gap-1 text-xs font-medium capitalize ${priorityColor[t.priority]}`}>
                          <Zap size={10} />{t.priority}
                        </span>
                      )}
                      {t.category && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground capitalize">
                          <Tag size={10} />{t.category}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant={statusColor[t.status] ?? 'outline'} className="capitalize text-xs">
                      {t.status.replace('_', ' ')}
                    </Badge>
                    <ChevronRight size={15} className="text-muted-foreground/50 group-hover:text-muted-foreground transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>

        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(o => o - limit)}>
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              {offset + 1}–{Math.min(offset + limit, total)} of {total}
            </span>
            <Button variant="outline" size="sm" disabled={offset + limit >= total} onClick={() => setOffset(o => o + limit)}>
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
