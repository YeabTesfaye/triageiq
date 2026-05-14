import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import {
  Plus,
  ChevronRight,
  Ticket,
  Zap,
  Tag,
  Search,
  X,
  ArrowUpDown,
} from 'lucide-react'
import { TicketsListSkeleton } from '@/components/ui/loading'

// ─── Types ────────────────────────────────────────────────────────────────────
interface TicketItem {
  id: string
  message: string
  category: string | null
  priority: string | null
  status: string
  created_at: string
}

interface TicketListResponse {
  items: TicketItem[]
  total: number
}

// ─── Constants ────────────────────────────────────────────────────────────────
const LIMIT = 10

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

const PRIORITY_META: Record<
  string,
  { label: string; textClass: string; dotClass: string }
> = {
  all:    { label: 'All',    textClass: '',                                       dotClass: '' },
  high:   { label: 'High',   textClass: 'text-red-600 dark:text-red-400',        dotClass: 'bg-red-500' },
  medium: { label: 'Medium', textClass: 'text-yellow-600 dark:text-yellow-400',  dotClass: 'bg-yellow-500' },
  low:    { label: 'Low',    textClass: 'text-green-600 dark:text-green-400',    dotClass: 'bg-green-500' },
}

const SORT_OPTIONS = [
  { value: 'created_at:desc', label: 'Newest first' },
  { value: 'created_at:asc',  label: 'Oldest first' },
  { value: 'priority:desc',   label: 'Priority: High first' },
  { value: 'priority:asc',    label: 'Priority: Low first' },
] as const

// ─── Helpers ──────────────────────────────────────────────────────────────────
function formatRelativeTime(dateStr: string): string {
  const diffSec = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (diffSec < 60)     return 'just now'
  if (diffSec < 3600)   return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400)  return `${Math.floor(diffSec / 3600)}h ago`
  if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function useDebounce<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function TicketsPage() {
  // ── URL-driven filter state ───────────────────────────────────────────────
  const [searchParams, setSearchParams] = useSearchParams()

  const status   = searchParams.get('status')   ?? 'all'
  const priority = searchParams.get('priority') ?? 'all'
  const sort     = searchParams.get('sort')     ?? 'created_at'
  const order    = searchParams.get('order')    ?? 'desc'
  const page     = Math.max(0, parseInt(searchParams.get('page') ?? '0', 10))

  // `search` is the committed value (in URL); `searchInput` is the live
  // local state. The debounced version writes to the URL which triggers fetch.
  const search = searchParams.get('q') ?? ''
  const [searchInput, setSearchInput] = useState(search)
  const debouncedSearch = useDebounce(searchInput)

  // ── Data state ────────────────────────────────────────────────────────────
  const [tickets, setTickets] = useState<TicketItem[]>([])
  const [total, setTotal]     = useState(0)

  // Instead of calling setLoading(true) inside the effect (which triggers a
  // cascading render), we derive loading state from a ref-tracked fetch ID.
  // `fetchId` increments on every fetch trigger; `settledId` catches up when
  // the response arrives. loading = fetchId !== settledId.
  const fetchIdRef    = useRef(0)
  const [settledId, setSettledId] = useState(0)
  const loading = fetchIdRef.current !== settledId

  const [initialized, setInitialized] = useState(false)

  // ── URL helpers ───────────────────────────────────────────────────────────
  const setParam = (key: string, value: string, resetPage = true) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (value === 'all' || value === '') next.delete(key)
      else next.set(key, value)
      if (resetPage) next.delete('page')
      return next
    })
  }

  const clearAllFilters = () => {
    setSearchInput('')
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('status')
      next.delete('priority')
      next.delete('q')
      next.delete('page')
      return next
    })
  }

  // ── Sync debounced search → URL ───────────────────────────────────────────
  useEffect(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (debouncedSearch) next.set('q', debouncedSearch)
        else next.delete('q')
        next.delete('page')
        return next
      },
      { replace: true },
    )
  }, [debouncedSearch]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Fetch ─────────────────────────────────────────────────────────────────
  // We increment fetchIdRef synchronously (no setState) so `loading` becomes
  // true immediately on the next render without a separate setState call inside
  // the effect body. settledId catching up is what clears the loading state.
  useEffect(() => {
    // Increment ref synchronously — this is not a setState call, so it does
    // not cause a cascading render. The component re-renders because searchParams
    // changed, and at that point fetchIdRef.current !== settledId → loading=true.
    fetchIdRef.current += 1
    const thisId = fetchIdRef.current

    const params = new URLSearchParams({
      limit:  String(LIMIT),
      offset: String(page * LIMIT),
      sort,
      order,
    })
    if (status !== 'all')   params.set('status', status)
    if (priority !== 'all') params.set('priority', priority)
    if (search)             params.set('search', search)

    api
      .get<TicketListResponse>(`/ticket?${params.toString()}`)
      .then((r) => {
        // Discard stale responses from superseded fetches
        if (thisId !== fetchIdRef.current) return
        setTickets(r.data.items ?? [])
        setTotal(r.data.total ?? 0)
      })
      .finally(() => {
        if (thisId !== fetchIdRef.current) return
        setSettledId(thisId)
        setInitialized(true)
      })
  }, [status, priority, search, sort, order, page])
  // ── Derived values ────────────────────────────────────────────────────────
  const activeFilterCount = [
    status !== 'all',
    priority !== 'all',
    Boolean(search),
  ].filter(Boolean).length

  const totalPages = Math.ceil(total / LIMIT)
  const sortKey    = `${sort}:${order}`

  if (!initialized && loading) return <TicketsListSkeleton />

  return (
    <div className="space-y-4">
      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tickets</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {loading
              ? 'Loading…'
              : `${total} ticket${total !== 1 ? 's' : ''}${activeFilterCount > 0 ? ' matching filters' : ''}`}
          </p>
        </div>
      </div>

      {/* ── Filter bar ──────────────────────────────────────────────────────── */}
      <div className="space-y-2">
        {/* Row 1: Search + Status + Sort + Clear */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative flex-1 min-w-50 max-w-sm">
            <Search
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
            />
            <Input
              placeholder="Search by title, category, or ID…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-8 h-8 text-sm"
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                aria-label="Clear search"
              >
                <X size={13} />
              </button>
            )}
          </div>

          {/* Status filter */}
          <Select value={status} onValueChange={(v) => setParam('status', v)}>
            <SelectTrigger className="w-36 h-8 text-sm">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="open">Open</SelectItem>
              <SelectItem value="in_progress">In progress</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
              <SelectItem value="closed">Closed</SelectItem>
            </SelectContent>
          </Select>

          {/* Sort */}
          <Select
            value={sortKey}
            onValueChange={(v) => {
              const colonIdx = v.indexOf(':')
              const s = v.slice(0, colonIdx)
              const o = v.slice(colonIdx + 1)
              setSearchParams((prev) => {
                const next = new URLSearchParams(prev)
                next.set('sort', s)
                next.set('order', o)
                return next
              })
            }}
          >
            <SelectTrigger className="w-44 h-8 text-sm">
              <ArrowUpDown size={12} className="mr-1.5 text-muted-foreground shrink-0" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {activeFilterCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearAllFilters}
              className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2"
            >
              <X size={12} />
              Clear {activeFilterCount} {activeFilterCount === 1 ? 'filter' : 'filters'}
            </Button>
          )}
        </div>

        {/* Row 2: Priority pill filters */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground mr-0.5 shrink-0">Priority:</span>
          {(['all', 'high', 'medium', 'low'] as const).map((p) => {
            const meta     = PRIORITY_META[p]
            const isActive = priority === p
            return (
              <button
                key={p}
                onClick={() => setParam('priority', p)}
                className={[
                  'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border transition-all',
                  isActive
                    ? 'bg-foreground text-background border-foreground'
                    : 'bg-transparent text-muted-foreground border-border hover:border-foreground/50 hover:text-foreground',
                ].join(' ')}
              >
                {p !== 'all' && (
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      isActive ? 'bg-background' : meta.dotClass
                    }`}
                  />
                )}
                {meta.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Ticket list ─────────────────────────────────────────────────────── */}
      <Card
        className={
          loading
            ? 'opacity-60 pointer-events-none transition-opacity'
            : 'transition-opacity'
        }
      >
        <CardContent className="p-0">
          {tickets.length === 0 && !loading ? (
            <div className="text-center py-16">
              <Ticket size={36} className="mx-auto text-muted-foreground/30 mb-3" />
              {activeFilterCount > 0 ? (
                <>
                  <p className="text-sm font-medium text-muted-foreground">
                    No tickets match your filters
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1 mb-4">
                    Try adjusting or clearing your active filters.
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={clearAllFilters}
                    className="gap-2"
                  >
                    <X size={14} />
                    Clear filters
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-muted-foreground">
                    No tickets yet
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1 mb-4">
                    Submit your first ticket and the AI will triage it automatically.
                  </p>
                  <Link to="/tickets/new">
                    <Button variant="outline" size="sm" className="gap-2">
                      <Plus size={14} />
                      Create your first ticket
                    </Button>
                  </Link>
                </>
              )}
            </div>
          ) : (
            <div className="divide-y">
              {tickets.map((t) => (
                <Link
                  key={t.id}
                  to={`/tickets/${t.id}`}
                  className="flex items-center gap-3 px-4 py-3.5 hover:bg-muted/50 transition-colors group"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                      {t.message?.slice(0, 100)}
                      {t.message?.length > 100 ? '…' : ''}
                    </p>
                    <div className="flex items-center gap-3 mt-1.5 flex-wrap">
                      <span
                        className="text-xs text-muted-foreground"
                        title={new Date(t.created_at).toLocaleString()}
                      >
                        {formatRelativeTime(t.created_at)}
                      </span>
                      {t.priority && (
                        <span
                          className={`flex items-center gap-1 text-xs font-medium capitalize ${
                            PRIORITY_META[t.priority]?.textClass ?? ''
                          }`}
                        >
                          <Zap size={10} />
                          {t.priority}
                        </span>
                      )}
                      {t.category && (
                        <span className="flex items-center gap-1 text-xs text-muted-foreground capitalize">
                          <Tag size={10} />
                          {t.category}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Badge
                      variant="outline"
                      className={`capitalize text-xs ${statusBadgeClass[t.status] ?? ''}`}
                    >
                      {t.status.replace('_', ' ')}
                    </Badge>
                    <ChevronRight
                      size={15}
                      className="text-muted-foreground/30 group-hover:text-muted-foreground transition-colors"
                    />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>

        {/* ── Pagination ────────────────────────────────────────────────────── */}
        {total > LIMIT && (
          <div className="flex items-center justify-between px-4 py-3 border-t">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0 || loading}
              onClick={() => setParam('page', String(page - 1), false)}
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {page + 1} of {totalPages} · {total} ticket{total !== 1 ? 's' : ''}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages - 1 || loading}
              onClick={() => setParam('page', String(page + 1), false)}
            >
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
