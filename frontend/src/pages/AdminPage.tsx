import { useEffect, useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { ShieldCheck, Users, Ticket, ScrollText, ChevronRight, UserPlus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

// ─── Types ────────────────────────────────────────────────────────────────────

interface AdminUser {
  id: string
  full_name: string
  email: string
  role: 'superadmin' | 'admin' | 'moderator' | 'user'
  status: 'active' | 'suspended' | 'banned'
}

interface AdminTicket {
  id: string
  message: string
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  priority: 'high' | 'medium' | 'low' | null
  category: string | null
  created_at: string
}

interface AuditLog {
  id: string
  action: string
  target_type: string
  actor_role: string
  created_at: string
}

interface PaginatedResponse<T> {
  items: T[]
  meta: { total: number }
}

interface AdminData {
  users: AdminUser[]
  userTotal: number
  tickets: AdminTicket[]
  ticketTotal: number
  logs: AuditLog[]
  logTotal: number
}

const EMPTY_DATA: AdminData = {
  users: [], userTotal: 0,
  tickets: [], ticketTotal: 0,
  logs: [], logTotal: 0,
}

// ─── Badge colour maps ────────────────────────────────────────────────────────

const roleColor: Record<AdminUser['role'], 'default' | 'secondary' | 'outline'> = {
  superadmin: 'default',
  admin: 'secondary',
  moderator: 'outline',
  user: 'outline',
}

const ticketStatusColor: Record<AdminTicket['status'], 'default' | 'secondary' | 'destructive' | 'outline'> = {
  open: 'destructive',
  in_progress: 'secondary',
  resolved: 'default',
  closed: 'outline',
}

const priorityColor: Record<'high' | 'medium' | 'low', string> = {
  high: 'text-red-500',
  medium: 'text-yellow-500',
  low: 'text-green-500',
}

// ─── User row ─────────────────────────────────────────────────────────────────

interface UserRowProps {
  user: AdminUser
  onStatusChange: () => void
}

function UserRow({ user, onStatusChange }: UserRowProps) {
  const { user: me } = useAuth()
  const isSelf = me?.id === user.id
  const canChangeStatus = !isSelf && (me?.role === 'admin' || me?.role === 'superadmin')

  const changeStatus = async (status: AdminUser['status']) => {
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
        <Badge variant={roleColor[user.role]} className="capitalize text-xs">
          {user.role}
        </Badge>

        {user.status === 'active' ? (
          <span className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full bg-green-500/10 text-green-600 capitalize">
            <span className="w-1.5 h-1.5 rounded-full bg-green-600 shrink-0" />
            active
          </span>
        ) : (
          <Badge variant="destructive" className="capitalize text-xs">
            {user.status}
          </Badge>
        )}

        {canChangeStatus && (
          <Select value={user.status} onValueChange={changeStatus}>
            <SelectTrigger className="h-7 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(['active', 'suspended', 'banned'] as AdminUser['status'][]).map((s) => (
                <SelectItem key={s} value={s} className="text-xs capitalize">{s}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  )
}

// ─── Ticket row ───────────────────────────────────────────────────────────────

function TicketRow({ ticket }: { ticket: AdminTicket }) {
  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors group"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
          {ticket.message?.slice(0, 80)}...
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-muted-foreground">
            {new Date(ticket.created_at).toLocaleDateString()}
          </span>
          {ticket.priority && (
            <span className={`text-xs font-medium capitalize ${priorityColor[ticket.priority]}`}>
              · {ticket.priority}
            </span>
          )}
          {ticket.category && (
            <span className="text-xs text-muted-foreground capitalize">
              · {ticket.category}
            </span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Badge variant={ticketStatusColor[ticket.status]} className="capitalize text-xs">
          {ticket.status.replace('_', ' ')}
        </Badge>
        <ChevronRight size={14} className="text-muted-foreground/50" />
      </div>
    </Link>
  )
}

// ─── Empty state ──────────────────────────────────────────────────────────────

interface EmptyStateProps {
  icon: React.ElementType
  title: string
  description: string
  action?: React.ReactNode
}

function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-6 gap-3 text-center">
      <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center mb-1">
        <Icon size={26} className="text-muted-foreground" />
      </div>
      <p className="text-[15px] font-semibold">{title}</p>
      <p className="text-[13px] text-muted-foreground max-w-[280px] leading-relaxed">{description}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'superadmin'

  const [data, setData] = useState<AdminData>(EMPTY_DATA)
  const [loading, setLoading] = useState(true)
  // Incrementing this triggers a refetch without useCallback
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let active = true

    async function load() {
      try {


        const [usersRes, ticketsRes] = await Promise.all([
        api.get<PaginatedResponse<AdminUser>>('/admin/users?limit=20'),
          api.get<PaginatedResponse<AdminTicket>>('/admin/ticket?limit=20'),
        ])

        const logsRes = isSuperAdmin
          ? await api.get<PaginatedResponse<AuditLog>>('/admin/audit-logs?limit=20')
          : null

        if (!active) return

        setData({
          users:       usersRes.data.items,
          userTotal:   usersRes.data.meta.total,
          tickets:     ticketsRes.data.items,
          ticketTotal: ticketsRes.data.meta.total,
          logs:        logsRes?.data.items   ?? [],
          logTotal:    logsRes?.data.meta.total ?? 0,
        })
      } catch (err) {
        console.error('[AdminPage] load failed:', err)
      } finally {
        if (active) setLoading(false)
      }
    }

    load()
    return () => { active = false }
  }, [refreshKey, isSuperAdmin])

  if (loading) return <AdminSkeleton />

  const { users, userTotal, tickets, ticketTotal, logs, logTotal } = data

  const statCards = [
    { label: 'Total Users',   value: userTotal,   icon: Users,      iconColor: 'text-blue-500',   iconBg: 'bg-blue-500/10'   },
    { label: 'Total Tickets', value: ticketTotal, icon: Ticket,     iconColor: 'text-violet-500', iconBg: 'bg-violet-500/10' },
    ...(isSuperAdmin
      ? [{ label: 'Audit Logs', value: logTotal, icon: ScrollText, iconColor: 'text-orange-500', iconBg: 'bg-orange-500/10' }]
      : []),
  ]

  const tabs = [
    { value: 'users',   label: 'Users',     icon: Users },
    { value: 'tickets', label: 'Tickets',   icon: Ticket },
    ...(isSuperAdmin ? [{ value: 'audit', label: 'Audit Log', icon: ScrollText }] : []),
  ]

  return (
    <div className="flex flex-col gap-6">
      {/* ── Page header ── */}
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 rounded-xl bg-blue-500 flex items-center justify-center shrink-0">
          <ShieldCheck size={22} color="#fff" />
        </div>
        <div>
          <h1 className="text-[22px] font-semibold tracking-tight leading-tight">Admin Panel</h1>
          <p className="text-[13px] text-muted-foreground mt-0.5">Manage users, tickets, and audit logs</p>
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {statCards.map(({ label, value, icon: Icon, iconColor, iconBg }) => (
          <Card key={label}>
            <CardContent className="pt-5 pb-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
                  {label}
                </span>
                <div className={`w-8 h-8 rounded-lg ${iconBg} flex items-center justify-center`}>
                  <Icon size={16} className={iconColor} />
                </div>
              </div>
              <p className="text-[32px] font-semibold tracking-tight leading-none">{value}</p>
              <p className="text-xs text-muted-foreground mt-1.5">—</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Tabs ── */}
      <Tabs defaultValue="users">
        <TabsList className="bg-transparent border-b border-border rounded-none p-0 h-auto gap-0 w-full justify-start">
          {tabs.map(({ value, label, icon: Icon }) => (
            <TabsTrigger
              key={value}
              value={value}
              className="rounded-none bg-transparent border-none border-b-2 border-b-transparent px-4 py-2 text-[13px] font-medium text-muted-foreground flex items-center gap-1.5 transition-colors data-[state=active]:text-foreground data-[state=active]:border-b-blue-500 data-[state=active]:shadow-none"
            >
              <Icon size={13} />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Users */}
        <TabsContent value="users" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-[13px] text-muted-foreground font-normal">
                {userTotal} {userTotal === 1 ? 'user' : 'users'} total
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {users.length === 0 ? (
                <EmptyState
                  icon={UserPlus}
                  title="No users yet"
                  description="Users will appear here once they register for an account."
                  action={
                    <Button size="sm" className="bg-blue-500 text-white font-medium text-[13px]">
                      <UserPlus size={14} className="mr-1.5" />
                      Invite user
                    </Button>
                  }
                />
              ) : (
                <div className="divide-y">
                  {users.map((u) => (
                    <UserRow key={u.id} user={u} onStatusChange={() => setRefreshKey((k) => k + 1)} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tickets */}
        <TabsContent value="tickets" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-[13px] text-muted-foreground font-normal">
                {ticketTotal} {ticketTotal === 1 ? 'ticket' : 'tickets'} total
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {tickets.length === 0 ? (
                <EmptyState
                  icon={Ticket}
                  title="No tickets yet"
                  description="Support tickets submitted by users will appear here."
                />
              ) : (
                <div className="divide-y">
                  {tickets.map((t) => <TicketRow key={t.id} ticket={t} />)}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit log */}
        {isSuperAdmin && (
          <TabsContent value="audit" className="mt-4">
            <Card>
              <CardContent className="p-0">
                {logs.length === 0 ? (
                  <EmptyState
                    icon={ScrollText}
                    title="No audit logs yet"
                    description="Admin actions and system events will be recorded here."
                  />
                ) : (
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
                          <Badge variant="outline" className="capitalize text-xs shrink-0">
                            {log.actor_role}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function AdminSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-11 w-11 rounded-xl" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-52" />
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-5 pb-5">
              <div className="flex items-center justify-between mb-3">
                <Skeleton className="h-3 w-20" />
                <Skeleton className="h-8 w-8 rounded-lg" />
              </div>
              <Skeleton className="h-9 w-14" />
              <Skeleton className="h-3 w-8 mt-2" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="flex gap-4 border-b">
        {[80, 64, 80].map((w, i) => (
          <Skeleton key={i} className="h-4 mb-2" style={{ width: w }} />
        ))}
      </div>
      <Card>
        <CardContent className="p-0">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-4 py-3 flex items-center gap-3 border-b last:border-0">
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-52" />
              </div>
              <Skeleton className="h-5 w-14 rounded-full" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
