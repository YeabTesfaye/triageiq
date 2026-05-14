import { useCallback, useEffect, useRef, useState } from 'react'
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
  role: string
  status: string
}

interface AdminTicket {
  id: string
  message: string
  status: string
  priority: string | null
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

// ─── Badge colour maps ────────────────────────────────────────────────────────

const roleColor: Record<string, 'default' | 'secondary' | 'outline'> = {
  superadmin: 'default',
  admin: 'secondary',
  moderator: 'outline',
  user: 'outline',
}

const ticketStatusColor: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  open: 'destructive',
  in_progress: 'secondary',
  resolved: 'default',
  closed: 'outline',
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
        <Badge variant={roleColor[user.role] ?? 'outline'} className="capitalize text-xs">
          {user.role}
        </Badge>

        {user.status === 'active' ? (
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '11px',
              fontWeight: 500,
              padding: '2px 8px',
              borderRadius: '999px',
              background: 'hsl(142 76% 36% / 0.1)',
              color: 'hsl(142 76% 36%)',
              textTransform: 'capitalize',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: 'hsl(142 76% 36%)',
                flexShrink: 0,
              }}
            />
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
              {['active', 'suspended', 'banned'].map((s) => (
                <SelectItem key={s} value={s} className="text-xs capitalize">
                  {s}
                </SelectItem>
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
  const priorityColor: Record<string, string> = {
    high: 'text-red-500',
    medium: 'text-yellow-500',
    low: 'text-green-500',
  }

  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className="flex items-center gap-3 px-4 py-3 hover:bg-muted/50 transition-colors group"
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
          {ticket.message?.slice(0, 80)}…
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
        <Badge
          variant={ticketStatusColor[ticket.status] ?? 'outline'}
          className="capitalize text-xs"
        >
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
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        gap: '12px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: '56px',
          height: '56px',
          borderRadius: '16px',
          background: 'hsl(var(--muted))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '4px',
        }}
      >
        <Icon size={26} style={{ color: 'hsl(var(--muted-foreground))' }} />
      </div>
      <p style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>{title}</p>
      <p
        style={{
          fontSize: '13px',
          color: 'hsl(var(--muted-foreground))',
          margin: 0,
          maxWidth: '280px',
          lineHeight: 1.5,
        }}
      >
        {description}
      </p>
      {action && <div style={{ marginTop: '4px' }}>{action}</div>}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AdminPage() {
  const { user } = useAuth()

  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([])
  const [tickets, setTickets] = useState<AdminTicket[]>([])
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(true)
  const [userTotal, setUserTotal] = useState(0)
  const [ticketTotal, setTicketTotal] = useState(0)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [logTotal, setLogTotal] = useState(0)

  const isSuperAdmin = user?.role === 'superadmin'

  // Stable ref so fetchAll (memoised) always reads the latest value
  // without needing isSuperAdmin in the dependency array.
  const isSuperAdminRef = useRef(isSuperAdmin)
  // eslint-disable-next-line react-hooks/refs
  isSuperAdminRef.current = isSuperAdmin

  // Memoised so the reference is stable across renders; safe to list in the
  // useEffect dependency array and to pass as a prop to UserRow.
 const fetchAll = useCallback(async () => {
  const promises = [
    api.get('/admin/users?limit=20'),
    api.get('/admin/ticket?limit=20'),
  ]
  if (isSuperAdminRef.current) {
    promises.push(api.get('/admin/audit-logs?limit=20'))
  }

  const results = await Promise.all(promises)

  // ── Defensive: handle both { items, meta } and { data: { items, meta } }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const unwrap = (r: any) => r?.data ?? r

  const usersPayload  = unwrap(results[0])
  const ticketsPayload = unwrap(results[1])
  const logsPayload   = isSuperAdminRef.current ? unwrap(results[2]) : null

  const nextUsers     = (usersPayload?.items  ?? []) as AdminUser[]
  const nextUserTotal = (usersPayload?.meta?.total ?? 0) as number
  const nextTickets   = (ticketsPayload?.items ?? []) as AdminTicket[]
  const nextTktTotal  = (ticketsPayload?.meta?.total ?? 0) as number
  const nextLogs      = (logsPayload?.items   ?? []) as AuditLog[]
  const nextLogTotal  = (logsPayload?.meta?.total ?? 0) as number   // ← was logs.length

  setAdminUsers(nextUsers)
  setUserTotal(nextUserTotal)
  setTickets(nextTickets)
  setTicketTotal(nextTktTotal)
  setLogs(nextLogs)
  setLogTotal(nextLogTotal)    // ← new state
}, [])

  useEffect(() => {
    // `active` flag prevents setState being called after the component unmounts
    // (e.g. user navigates away before the fetch resolves).
    let active = true

    async function load() {
  try {
    await fetchAll()
  } catch (err) {
    console.error('[AdminPage] fetchAll failed:', err)  // ← tells you the real problem
  } finally {
    if (active) setLoading(false)
  }
  }

    load()

    return () => {
      active = false
    }
  }, [fetchAll])

  if (loading) return <AdminSkeleton />

  const statCards = [
    {
      label: 'Total Users',
      value: userTotal,
      icon: Users,
      iconColor: '#3B82F6',
      iconBg: 'hsl(217 91% 60% / 0.1)',
    },
    {
      label: 'Total Tickets',
      value: ticketTotal,
      icon: Ticket,
      iconColor: 'hsl(262 83% 58%)',
      iconBg: 'hsl(262 83% 58% / 0.1)',
    },
    ...(isSuperAdmin
      ? [
          {
            label: 'Audit Logs',
            value: logs.length,
            icon: ScrollText,
            iconColor: 'hsl(25 95% 53%)',
            iconBg: 'hsl(25 95% 53% / 0.1)',
          },
        ]
      : []),
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* ── Page header ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div
          style={{
            width: '44px',
            height: '44px',
            borderRadius: '12px',
            background: 'hsl(217 91% 60%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <ShieldCheck size={22} color="#fff" />
        </div>
        <div>
          <h1
            style={{
              fontSize: '22px',
              fontWeight: 600,
              letterSpacing: '-0.01em',
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            Admin Panel
          </h1>
          <p
            style={{
              fontSize: '13px',
              color: 'hsl(var(--muted-foreground))',
              margin: '2px 0 0',
            }}
          >
            Manage users, tickets, and audit logs
          </p>
        </div>
      </div>

      {/* ── Stat cards ── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${statCards.length}, 1fr)`,
          gap: '16px',
        }}
      >
        {statCards.map(({ label, value, icon: Icon, iconColor, iconBg }) => (
          <Card key={label}>
            <CardContent style={{ paddingTop: '20px', paddingBottom: '20px' }}>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '12px',
                }}
              >
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 500,
                    textTransform: 'uppercase',
                    letterSpacing: '0.06em',
                    color: 'hsl(var(--muted-foreground))',
                  }}
                >
                  {label}
                </span>
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: iconBg,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Icon size={16} style={{ color: iconColor }} />
                </div>
              </div>
              <p
                style={{
                  fontSize: '32px',
                  fontWeight: 600,
                  letterSpacing: '-0.02em',
                  margin: 0,
                  lineHeight: 1,
                }}
              >
                {value}
              </p>
              <p
                style={{
                  fontSize: '12px',
                  color: 'hsl(var(--muted-foreground))',
                  margin: '6px 0 0',
                }}
              >
                —
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* ── Tabs ── */}
      <Tabs defaultValue="users">
        <TabsList
          style={{
            background: 'transparent',
            borderBottom: '1px solid hsl(var(--border))',
            borderRadius: 0,
            padding: 0,
            height: 'auto',
            gap: 0,
            width: '100%',
            justifyContent: 'flex-start',
          }}
        >
          {[
            { value: 'users',   label: 'Users',     icon: Users },
            { value: 'tickets', label: 'Tickets',   icon: Ticket },
            ...(isSuperAdmin
              ? [{ value: 'audit', label: 'Audit Log', icon: ScrollText }]
              : []),
          ].map(({ value, label, icon: Icon }) => (
            <TabsTrigger
              key={value}
              value={value}
              style={{
                borderRadius: 0,
                background: 'transparent',
                border: 'none',
                borderBottom: '2px solid transparent',
                padding: '8px 16px',
                fontSize: '13px',
                fontWeight: 500,
                color: 'hsl(var(--muted-foreground))',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'color 0.15s ease',
              }}
              className="data-[state=active]:text-foreground data-[state=active]:border-b-[2px] data-[state=active]:border-b-blue-500 data-[state=active]:shadow-none"
            >
              <Icon size={13} />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* Users */}
        <TabsContent value="users" style={{ marginTop: '16px' }}>
          <Card>
            <CardHeader style={{ paddingBottom: '8px' }}>
              <CardTitle
                style={{ fontSize: '13px', color: 'hsl(var(--muted-foreground))', fontWeight: 400 }}
              >
                {userTotal} {userTotal === 1 ? 'user' : 'users'} total
              </CardTitle>
            </CardHeader>
            <CardContent style={{ padding: 0 }}>
              {adminUsers.length === 0 ? (
                <EmptyState
                  icon={UserPlus}
                  title="No users yet"
                  description="Users will appear here once they register for an account."
                  action={
                    <Button
                      size="sm"
                      style={{
                        backgroundColor: 'hsl(217 91% 60%)',
                        color: '#fff',
                        border: 'none',
                        fontWeight: 500,
                        fontSize: '13px',
                      }}
                    >
                      <UserPlus size={14} style={{ marginRight: '6px' }} />
                      Invite user
                    </Button>
                  }
                />
              ) : (
                <div className="divide-y">
                  {adminUsers.map((u) => (
                    <UserRow key={u.id} user={u} onStatusChange={fetchAll} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tickets */}
        <TabsContent value="tickets" style={{ marginTop: '16px' }}>
          <Card>
            <CardHeader style={{ paddingBottom: '8px' }}>
              <CardTitle
                style={{ fontSize: '13px', color: 'hsl(var(--muted-foreground))', fontWeight: 400 }}
              >
                {ticketTotal} {ticketTotal === 1 ? 'ticket' : 'tickets'} total
              </CardTitle>
            </CardHeader>
            <CardContent style={{ padding: 0 }}>
              {tickets.length === 0 ? (
                <EmptyState
                  icon={Ticket}
                  title="No tickets yet"
                  description="Support tickets submitted by users will appear here."
                />
              ) : (
                <div className="divide-y">
                  {tickets.map((t) => (
                    <TicketRow key={t.id} ticket={t} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit log */}
        {isSuperAdmin && (
          <TabsContent value="audit" style={{ marginTop: '16px' }}>
            <Card>
              <CardContent style={{ padding: 0 }}>
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
                            <p className="text-sm font-medium">
                              {log.action.replace('.', ' › ')}
                            </p>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div className="flex items-center gap-4">
        <Skeleton className="h-11 w-11 rounded-xl" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-36" />
          <Skeleton className="h-4 w-52" />
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <Card key={i}>
            <CardContent style={{ paddingTop: '20px', paddingBottom: '20px' }}>
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

      <div className="flex gap-4 border-b pb-0">
        {[80, 64, 80].map((w, i) => (
          <Skeleton key={i} className="h-4 mb-2" style={{ width: `${w}px` }} />
        ))}
      </div>

      <Card>
        <CardContent style={{ padding: 0 }}>
          {[...Array(5)].map((_, i) => (
            <div
              key={i}
              className="px-4 py-3 flex items-center gap-3 border-b last:border-0"
              style={{
                animation: 'shimmer 1.5s ease-in-out infinite',
                animationDelay: `${i * 0.1}s`,
              }}
            >
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

      <style>{`
        @keyframes shimmer {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}
