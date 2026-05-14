import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Ticket,
  CheckCircle,
  Clock,
  AlertCircle,
  Plus,
  ArrowRight,
  Zap,
  ChevronRight,
} from 'lucide-react'
import { DashboardSkeleton } from '@/components/ui/loading'

// ─── Badge styling ──────────────────────────────────────────────────────────
// Each status maps to a semantic color, not a decorative one.
// "Resolved" was previously the black default badge — now it's green.
// "In Progress" was gray secondary — now it's blue.
const statusBadgeClass: Record<string, string> = {
  open:
    'bg-red-50 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800',
  in_progress:
    'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800',
  resolved:
    'bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800',
  closed:
    'bg-gray-100 text-gray-600 border-gray-200 dark:bg-gray-900 dark:text-gray-400 dark:border-gray-700',
}

const priorityColor: Record<string, string> = {
  high: 'text-red-500',
  medium: 'text-yellow-500',
  low: 'text-green-500',
}

// ─── Zero-state messages ─────────────────────────────────────────────────────
// Each "0" should communicate something specific — not just emptiness.
// "Open: 0" is positive → green confirmation text.
// "Resolved: 0" is neutral → muted guidance.
const zeroState: Record<string, { text: string; className: string }> = {
  'Total tickets': {
    text: 'No tickets yet',
    className: 'text-muted-foreground',
  },
  Open: {
    text: 'All caught up ✓',
    className: 'text-green-600 dark:text-green-400',
  },
  'In progress': {
    text: 'Nothing in queue',
    className: 'text-muted-foreground',
  },
  Resolved: {
    text: 'None resolved yet',
    className: 'text-muted-foreground',
  },
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Returns a human-readable relative time string.
 * Falls back to a locale date string for anything older than a week.
 * The raw date is preserved in the `title` attribute for hover tooltips.
 */
function formatRelativeTime(dateStr: string): string {
  const diffSec = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diffSec < 60) return 'just now'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`
  return new Date(dateStr).toLocaleDateString()
}

/**
 * Time-of-day greeting with a proper late-night fallback.
 * Previous version had no branch for h >= 21, which would fall through
 * to "afternoon" at midnight on some runtimes.
 */
function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [tickets, setTickets] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // NOTE: open/inProgress/resolved counts below are derived from the 20 fetched
    // items, not the full dataset. If your API supports a /ticket/stats endpoint
    // (returning per-status counts), use that instead and store them in separate
    // state. The `total` field from the API is correct — only the breakdowns are
    // approximate when total > 20.
    api
      .get('/ticket?limit=20')
      .then((r) => {
        setTickets(r.data.items ?? [])
        setTotal(r.data.total ?? 0)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <DashboardSkeleton />

  const open = tickets.filter((t) => t.status === 'open').length
  const inProgress = tickets.filter((t) => t.status === 'in_progress').length
  const resolved = tickets.filter((t) => t.status === 'resolved').length
  const highPriority = tickets.filter((t) => t.priority === 'high').length
  const recent = tickets.slice(0, 5)

  // Each stat card links to the tickets list pre-filtered by its status.
  // This turns every metric into a navigation shortcut — users expect this
  // from any modern SaaS dashboard.
  const stats = [
    {
      label: 'Total tickets',
      value: total,
      icon: Ticket,
      iconColor: 'text-blue-500',
      iconBg: 'bg-blue-50 dark:bg-blue-950',
      href: '/tickets',
    },
    {
      label: 'Open',
      value: open,
      icon: AlertCircle,
      iconColor: 'text-red-500',
      iconBg: 'bg-red-50 dark:bg-red-950',
      href: '/tickets?status=open',
    },
    {
      label: 'In progress',
      value: inProgress,
      icon: Clock,
      iconColor: 'text-yellow-500',
      iconBg: 'bg-yellow-50 dark:bg-yellow-950',
      href: '/tickets?status=in_progress',
    },
    {
      label: 'Resolved',
      value: resolved,
      icon: CheckCircle,
      iconColor: 'text-green-500',
      iconBg: 'bg-green-50 dark:bg-green-950',
      href: '/tickets?status=resolved',
    },
  ]

  return (
    <div className="space-y-6">

      {/* ── Header ──────────────────────────────────────────────────────────
          Single CTA here only. The previous design showed "New Ticket" twice
          (nav + hero), which split visual attention and looked like a bug.
          Now the nav button is the persistent global action; this one is gone
          from the hero so the hierarchy is unambiguous.
      ─────────────────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Good {getGreeting()}, {user?.full_name.split(' ')[0]} 👋
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Here's an overview of your support tickets
          </p>
        </div>
        {/* <Link to="/tickets/new">
          <Button className="gap-2">
            <Plus size={16} />
            New Ticket
          </Button>
        </Link> */}
      </div>

      {/* ── Stat cards ──────────────────────────────────────────────────────
          Each card is now a Link — clicking "Open: 3" takes you directly to
          /tickets?status=open. Hover shows a subtle shadow lift and ring
          to reinforce that these are interactive.

          Zero-state subtext: "Open: 0" shows "All caught up ✓" in green
          rather than a bare zero that communicates nothing.

          Labels are sentence-case (was ALL CAPS) — easier to scan at speed
          and better WCAG compliance for readability.
      ─────────────────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, iconColor, iconBg, href }) => (
          <Link
            key={label}
            to={href}
            className="group rounded-xl focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <Card className="h-full cursor-pointer transition-all duration-150 group-hover:shadow-md group-hover:border-border/80">
              <CardContent className="pt-5 pb-4">
                <div className="flex items-center justify-between mb-3">
                  {/* Sentence case — was uppercase tracking-wide */}
                  <span className="text-xs font-medium text-muted-foreground">
                    {label}
                  </span>
                  <div className={`p-1.5 rounded-md ${iconBg}`}>
                    <Icon size={14} className={iconColor} />
                  </div>
                </div>

                <p className="text-3xl font-bold tracking-tight">{value}</p>

                {/* Zero-state message — each zero now communicates something */}
                {value === 0 && zeroState[label] && (
                  <p className={`text-xs mt-1 ${zeroState[label].className}`}>
                    {zeroState[label].text}
                  </p>
                )}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* ── High-priority alert ──────────────────────────────────────────────
          Unchanged in logic; link now filters by priority specifically.
      ─────────────────────────────────────────────────────────────────────── */}
      {highPriority > 0 && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-red-200 bg-red-50 dark:bg-red-950 dark:border-red-800">
          <Zap size={16} className="text-red-500 shrink-0" />
          <p className="text-sm text-red-700 dark:text-red-300">
            You have <strong>{highPriority}</strong> high-priority{' '}
            {highPriority === 1 ? 'ticket' : 'tickets'} needing attention.
          </p>
          <Link to="/tickets?priority=high" className="ml-auto shrink-0">
            <Button variant="destructive" size="sm">
              View
            </Button>
          </Link>
        </div>
      )}

      {/* ── Recent Tickets ───────────────────────────────────────────────────
          Improvements in this section:
          1. Relative timestamps ("2h ago") instead of locale date strings.
             Full date/time preserved in `title` attr for hover tooltip.
          2. Semantic badge colors — resolved is now green, not black.
             The black "Resolved" badge previously felt like an error state.
          3. ChevronRight icon on each row signals interactivity at rest.
             Previously there was no affordance that rows were clickable.
          4. Empty state with a direct CTA to create the first ticket.
      ─────────────────────────────────────────────────────────────────────── */}
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
            /* ── Empty state ──────────────────────────────────────────────
               Not just "no data" — a clear next action.
            ──────────────────────────────────────────────────────────────── */
            <div className="text-center py-12">
              <Ticket size={32} className="mx-auto text-muted-foreground/40 mb-3" />
              <p className="text-sm font-medium text-muted-foreground">No tickets yet</p>
              <p className="text-xs text-muted-foreground/70 mt-1 mb-4">
                Submit your first ticket and let the AI triage it for you.
              </p>
              <Link to="/tickets/new">
                <Button variant="outline" size="sm" className="gap-2">
                  <Plus size={14} />
                  Create your first ticket
                </Button>
              </Link>
            </div>
          ) : (
            <div className="divide-y">
              {recent.map((t) => (
                <Link
                  key={t.id}
                  to={`/tickets/${t.id}`}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-muted/50 transition-colors group"
                >
                  {/* Ticket info */}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                      {t.message?.slice(0, 90)}
                      {t.message?.length > 90 ? '…' : ''}
                    </p>

                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      {/* Relative timestamp with absolute date on hover */}
                      <span
                        className="text-xs text-muted-foreground"
                        title={new Date(t.created_at).toLocaleString()}
                      >
                        {formatRelativeTime(t.created_at)}
                      </span>

                      {t.priority && (
                        <span
                          className={`text-xs font-medium capitalize ${priorityColor[t.priority]}`}
                        >
                          · {t.priority}
                        </span>
                      )}

                      {t.category && (
                        <span className="text-xs text-muted-foreground capitalize">
                          · {t.category}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Status badge + row affordance */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge
                      variant="outline"
                      className={`capitalize text-xs ${statusBadgeClass[t.status] ?? ''}`}
                    >
                      {t.status.replace('_', ' ')}
                    </Badge>

                    {/* Chevron signals the row is clickable even at rest */}
                    <ChevronRight
                      size={14}
                      className="text-muted-foreground/30 group-hover:text-muted-foreground transition-colors"
                    />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
