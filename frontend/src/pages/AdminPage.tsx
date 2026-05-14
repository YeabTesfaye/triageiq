import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { ShieldCheck, Users, Ticket, ScrollText, ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

const roleColor: Record<string, 'default' | 'secondary' | 'outline'> = {
  superadmin: 'default', admin: 'secondary', moderator: 'outline', user: 'outline',
}
const statusColor: Record<string, 'default' | 'destructive' | 'outline'> = {
  active: 'default', suspended: 'destructive', banned: 'destructive',
}

function UserRow({ user, onStatusChange }: { user: any; onStatusChange: () => void }) {
  const { user: me } = useAuth()
  const isSelf = me?.id === user.id
  const canChangeStatus = !isSelf && (me?.role === 'admin' || me?.role === 'superadmin')

  const changeStatus = async (status: string) => {
    await api.patch(`/admin/users/${user.id}/status`, { status })
    onStatusChange()
  }

  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{user.full_name}</p>
          {isSelf && <span className="text-xs text-muted-foreground">(you)</span>}
        </div>
        <p className="text-xs text-muted-foreground truncate">{user.email}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Badge variant={roleColor[user.role] ?? 'outline'} className="capitalize text-xs">{user.role}</Badge>
        <Badge variant={statusColor[user.status] ?? 'outline'} className="capitalize text-xs">{user.status}</Badge>
        {canChangeStatus && (
          <Select value={user.status} onValueChange={changeStatus}>
            <SelectTrigger className="h-7 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {['active', 'suspended', 'banned'].map((s) => (
                <SelectItem key={s} value={s} className="text-xs capitalize">{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  )
}

function TicketRow({ ticket }: { ticket: any }) {
  const priorityColor: Record<string, string> = {
    high: 'text-red-500', medium: 'text-yellow-500', low: 'text-green-500',
  }
  const statusColor: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
    open: 'destructive', in_progress: 'secondary', resolved: 'default', closed: 'outline',
  }
  return (
    <Link to={`/tickets/${ticket.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors group">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
          {ticket.message?.slice(0, 80)}…
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-muted-foreground">{new Date(ticket.created_at).toLocaleDateString()}</span>
          {ticket.priority && (
            <span className={`text-xs font-medium capitalize ${priorityColor[ticket.priority]}`}>· {ticket.priority}</span>
          )}
          {ticket.category && (
            <span className="text-xs text-muted-foreground capitalize">· {ticket.category}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Badge variant={statusColor[ticket.status] ?? 'outline'} className="capitalize text-xs">
          {ticket.status.replace('_', ' ')}
        </Badge>
        <ChevronRight size={14} className="text-muted-foreground/50" />
      </div>
    </Link>
  )
}

export default function AdminPage() {
  const { user } = useAuth()
  const [users, setUsers] = useState<any[]>([])
  const [tickets, setTickets] = useState<any[]>([])
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [userTotal, setUserTotal] = useState(0)
  const [ticketTotal, setTicketTotal] = useState(0)

  const isSuperAdmin = user?.role === 'superadmin'

  const fetchAll = async () => {
    const promises: Promise<any>[] = [
      api.get('/admin/users?limit=20'),
      api.get('/admin/ticket?limit=20'),
    ]
    if (isSuperAdmin) promises.push(api.get('/admin/audit-logs?limit=20'))
    const results = await Promise.all(promises)
    setUsers(results[0].data.items ?? [])
    setUserTotal(results[0].data.meta?.total ?? 0)
    setTickets(results[1].data.items ?? [])
    setTicketTotal(results[1].data.meta?.total ?? 0)
    if (isSuperAdmin && results[2]) setLogs(results[2].data.items ?? [])
  }

  useEffect(() => {
    fetchAll().finally(() => setLoading(false))
  }, [])

  if (loading) return <AdminSkeleton />

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg bg-primary/10">
          <ShieldCheck size={20} className="text-primary" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin Panel</h1>
          <p className="text-sm text-muted-foreground">Manage users, tickets, and audit logs</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[
          { label: 'Total Users', value: userTotal, icon: Users, color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-950' },
          { label: 'Total Tickets', value: ticketTotal, icon: Ticket, color: 'text-purple-500', bg: 'bg-purple-50 dark:bg-purple-950' },
          ...(isSuperAdmin ? [{ label: 'Audit Logs', value: logs.length, icon: ScrollText, color: 'text-orange-500', bg: 'bg-orange-50 dark:bg-orange-950' }] : []),
        ].map(({ label, value, icon: Icon, color, bg }) => (
          <Card key={label}>
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</span>
                <div className={`p-1.5 rounded-md ${bg}`}><Icon size={14} className={color} /></div>
              </div>
              <p className="text-3xl font-bold tracking-tight">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users" className="gap-1.5"><Users size={13} />Users</TabsTrigger>
          <TabsTrigger value="tickets" className="gap-1.5"><Ticket size={13} />Tickets</TabsTrigger>
          {isSuperAdmin && <TabsTrigger value="audit" className="gap-1.5"><ScrollText size={13} />Audit Log</TabsTrigger>}
        </TabsList>

        <TabsContent value="users" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">{userTotal} users total</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y">
                {users.map((u) => (
                  <UserRow key={u.id} user={u} onStatusChange={fetchAll} />
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tickets" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">{ticketTotal} tickets total</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y">
                {tickets.map((t) => <TicketRow key={t.id} ticket={t} />)}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {isSuperAdmin && (
          <TabsContent value="audit" className="mt-4">
            <Card>
              <CardContent className="p-0">
                <div className="divide-y">
                  {logs.map((log) => (
                    <div key={log.id} className="px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-sm font-medium">{log.action.replace('.', ' › ')}</p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {log.target_type} · {new Date(log.created_at).toLocaleString()}
                          </p>
                        </div>
                        <Badge variant="outline" className="capitalize text-xs shrink-0">{log.actor_role}</Badge>
                      </div>
                    </div>
                  ))}
                  {logs.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-10">No audit logs yet</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

function AdminSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Skeleton className="h-10 w-10 rounded-lg" />
        <div className="space-y-2">
          <Skeleton className="h-7 w-36" />
          <Skeleton className="h-4 w-52" />
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i}><CardContent className="pt-5 pb-4">
            <div className="flex items-center justify-between mb-3">
              <Skeleton className="h-3 w-20" /><Skeleton className="h-7 w-7 rounded-md" />
            </div>
            <Skeleton className="h-9 w-12" />
          </CardContent></Card>
        ))}
      </div>
      <Skeleton className="h-10 w-64" />
      <Card><CardContent className="p-0">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="px-4 py-3 flex items-center gap-3 border-b">
            <div className="flex-1 space-y-2">
              <Skeleton className="h-4 w-40" /><Skeleton className="h-3 w-52" />
            </div>
            <Skeleton className="h-5 w-16 rounded-full" />
          </div>
        ))}
      </CardContent></Card>
    </div>
  )
}
