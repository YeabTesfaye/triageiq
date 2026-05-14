import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { ArrowLeft, Trash2, Bot, Tag, Zap, Clock, RefreshCw } from 'lucide-react'
import { TicketDetailSkeleton } from '@/components/ui/loading'

const statusColor: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  open: 'destructive',
  in_progress: 'secondary',
  resolved: 'default',
  closed: 'outline',
}

const priorityColor: Record<string, string> = {
  high: 'text-red-500 bg-red-50 border-red-200 dark:bg-red-950 dark:border-red-800',
  medium: 'text-yellow-600 bg-yellow-50 border-yellow-200 dark:bg-yellow-950 dark:border-yellow-800',
  low: 'text-green-600 bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800',
}

const categoryIcon: Record<string, string> = {
  billing: '💳',
  technical: '🔧',
  general: '💬',
}

export default function TicketDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [updating, setUpdating] = useState(false)
  const [polling, setPolling] = useState(false)

  const fetchTicket = async () => {
    const r = await api.get(`/ticket/${id}`)
    setTicket(r.data)
    return r.data
  }

  useEffect(() => {
    fetchTicket()
      .catch(() => navigate('/tickets'))
      .finally(() => setLoading(false))
  }, [id])

  // Poll if AI hasn't responded yet
  useEffect(() => {
    if (!ticket) return
    if (ticket.category || ticket.ai_response) return
    setPolling(true)
    const interval = setInterval(async () => {
      const t = await fetchTicket()
      if (t.category || t.ai_response) {
        setPolling(false)
        clearInterval(interval)
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [ticket?.id, ticket?.category])

  const updateStatus = async (status: string) => {
    setUpdating(true)
    try {
      const r = await api.patch(`/ticket/${id}`, { status })
      setTicket(r.data)
    } finally {
      setUpdating(false)
    }
  }

  const deleteTicket = async () => {
    if (!confirm('Delete this ticket? This cannot be undone.')) return
    await api.delete(`/ticket/${id}`)
    navigate('/tickets')
  }

  if (loading) return <TicketDetailSkeleton />
  if (!ticket) return null

  const hasAI = ticket.category || ticket.priority || ticket.ai_response

  return (
    <div className="max-w-2xl space-y-4">
      <Button variant="ghost" size="sm" className="gap-2 -ml-2" onClick={() => navigate(-1)}>
        <ArrowLeft size={15} /> Back to tickets
      </Button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Ticket Details</h1>
          <p className="text-xs text-muted-foreground font-mono mt-0.5">{ticket.id}</p>
        </div>
        <Badge variant={statusColor[ticket.status] ?? 'outline'} className="capitalize text-sm px-3 py-1">
          {ticket.status.replace('_', ' ')}
        </Badge>
      </div>

      {/* Message */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
            <Clock size={14} />
            Submitted {new Date(ticket.created_at).toLocaleString()}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{ticket.message}</p>
        </CardContent>
      </Card>

      {/* AI Analysis */}
      {!hasAI ? (
        <Card className="border-dashed">
          <CardContent className="flex items-center gap-3 py-5">
            <div className="p-2 rounded-full bg-muted">
              {polling ? (
                <RefreshCw size={16} className="text-muted-foreground animate-spin" />
              ) : (
                <Bot size={16} className="text-muted-foreground" />
              )}
            </div>
            <div>
              <p className="text-sm font-medium">
                {polling ? 'AI is analyzing your ticket…' : 'Awaiting AI analysis'}
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {polling ? 'This usually takes a few seconds' : 'Analysis will appear here shortly'}
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Bot size={15} className="text-primary" />
              AI Analysis
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {ticket.priority && (
                <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border ${priorityColor[ticket.priority] ?? ''}`}>
                  <Zap size={11} />
                  {ticket.priority.charAt(0).toUpperCase() + ticket.priority.slice(1)} Priority
                </span>
              )}
              {ticket.category && (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border bg-background">
                  <Tag size={11} />
                  {categoryIcon[ticket.category] ?? '📁'} {ticket.category.charAt(0).toUpperCase() + ticket.category.slice(1)}
                </span>
              )}
            </div>
            {ticket.ai_response && (
              <div className="text-sm leading-relaxed text-foreground/90 border-t pt-3">
                {ticket.ai_response}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <Card>
        <CardContent className="flex items-center gap-3 py-4">
          <div className="flex items-center gap-2 flex-1">
            <span className="text-sm text-muted-foreground shrink-0">Update status:</span>
            <Select value={ticket.status} onValueChange={updateStatus} disabled={updating}>
              <SelectTrigger className="w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {['open', 'in_progress', 'resolved', 'closed'].map((s) => (
                  <SelectItem key={s} value={s} className="capitalize">
                    {s.replace('_', ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="destructive" size="sm" className="gap-2" onClick={deleteTicket}>
            <Trash2 size={14} /> Delete
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
