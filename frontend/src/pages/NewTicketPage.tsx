import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ArrowLeft,
  CheckCircle2,
  Sparkles,
  Tag,
  Zap,
} from 'lucide-react'

// ─── Constants ────────────────────────────────────────────────────────────────
const MIN_CHARS = 20

// ─── Types ────────────────────────────────────────────────────────────────────
interface SuccessData {
  id: string
  priority: string | null
  category: string | null
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function humanPriority(p: string | null): string {
  if (!p) return 'Pending'
  return p.charAt(0).toUpperCase() + p.slice(1)
}

// ─── Auto-grow textarea hook ──────────────────────────────────────────────────
function useAutoGrow(value: string) {
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 400)}px`
  }, [value])

  return ref
}

// ─── Component ────────────────────────────────────────────────────────────────
export default function NewTicketPage() {
  const navigate = useNavigate()

  // ── Form state ───────────────────────────────────────────────────────────
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState<SuccessData | null>(null)
  const [showDiscard, setShowDiscard] = useState(false)

  const textareaRef = useAutoGrow(message)

  const charCount = message.length
  const isReady = charCount >= MIN_CHARS
  const progressPercent = Math.min((charCount / MIN_CHARS) * 100, 100)

  // ── Cancel guard ─────────────────────────────────────────────────────────
  function handleCancel() {
    if (message.trim().length > 0) {
      setShowDiscard(true)
    } else {
      navigate(-1)
    }
  }

  // ── Submit ───────────────────────────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!isReady || loading) return

    setLoading(true)
    setError('')

    try {
      const r = await api.post('/ticket', {
        message: message.trim(),
      })

      setSuccess({
        id: r.data.id,
        priority: r.data.priority ?? null,
        category: r.data.category ?? null,
      })
    } catch (err: unknown) {
      const detail =
        err instanceof Error
          ? err.message
          : (err as { response?: { data?: { detail?: string } } })?.response
              ?.data?.detail

      setError(detail ?? 'Failed to create ticket. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  // ── Success screen ───────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="max-w-2xl mx-auto mt-16 text-center space-y-6 px-4">
        <div className="flex justify-center">
          <span className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 dark:bg-green-950 text-green-600 dark:text-green-400">
            <CheckCircle2 size={36} />
          </span>
        </div>

        <div className="space-y-1.5">
          <h2 className="text-2xl font-semibold tracking-tight">
            Ticket created
          </h2>

          <p className="text-muted-foreground text-sm">
            Our AI has analysed your submission. Here's what we found:
          </p>
        </div>

        <div className="inline-flex items-center gap-6 border rounded-xl px-6 py-4 bg-card text-sm">
          <div className="text-left space-y-0.5">
            <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium">
              Priority
            </p>

            <p className="font-semibold flex items-center gap-1.5">
              <Zap
                size={13}
                className={
                  success.priority === 'high'
                    ? 'text-red-500'
                    : success.priority === 'medium'
                    ? 'text-yellow-500'
                    : 'text-green-500'
                }
              />

              {humanPriority(success.priority)}
            </p>
          </div>

          <div className="w-px h-8 bg-border" />

          <div className="text-left space-y-0.5">
            <p className="text-xs text-muted-foreground uppercase tracking-wide font-medium">
              Category
            </p>

            <p className="font-semibold flex items-center gap-1.5 capitalize">
              <Tag size={13} className="text-muted-foreground" />
              {success.category ?? 'Pending'}
            </p>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Our team has been notified and will respond shortly.
        </p>

        <div className="flex justify-center gap-3">
          <Button onClick={() => navigate(`/tickets/${success.id}`)}>
            View ticket
          </Button>

          <Button
            variant="outline"
            onClick={() => navigate('/tickets')}
          >
            All tickets
          </Button>
        </div>
      </div>
    )
  }

  // ── Loading screen ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="max-w-2xl mx-auto mt-24 text-center space-y-5 px-4">
        <div className="flex justify-center">
          <span className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-primary/10 text-primary animate-pulse">
            <Sparkles size={32} />
          </span>
        </div>

        <div className="space-y-1.5">
          <h2 className="text-xl font-semibold">
            Analysing your ticket…
          </h2>

          <p className="text-sm text-muted-foreground">
            Our AI is classifying priority and category. This takes a moment.
          </p>
        </div>

        <div className="w-48 mx-auto h-1 rounded-full bg-muted overflow-hidden">
          <div
            className="h-full bg-primary rounded-full animate-[progress_1.8s_ease-in-out_infinite]"
            style={{ width: '60%' }}
          />
        </div>
      </div>
    )
  }

  // ── Main form ────────────────────────────────────────────────────────────
  return (
    <>
      {/* Discard confirmation dialog */}
      {showDiscard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="bg-card border rounded-xl shadow-xl p-6 max-w-sm w-full mx-4 space-y-4">
            <h3 className="text-base font-semibold">
              Discard this ticket?
            </h3>

            <p className="text-sm text-muted-foreground">
              Your description will be lost.
            </p>

            <div className="flex gap-3 justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowDiscard(false)}
              >
                Keep editing
              </Button>

              <Button
                variant="destructive"
                size="sm"
                onClick={() => navigate(-1)}
              >
                Discard
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-3xl space-y-4">
        <Button
          variant="ghost"
          size="sm"
          className="gap-2"
          onClick={handleCancel}
        >
          <ArrowLeft size={15} />
          Back
        </Button>

        <Card>
          <CardHeader>
            <CardTitle>New Support Ticket</CardTitle>

            <CardDescription>
              Describe your issue and our AI will triage it automatically.
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form
              onSubmit={handleSubmit}
              className="space-y-5"
            >
              {/* ── Textarea ──────────────────────────────────────────────── */}
              <div className="space-y-2">
                <Label htmlFor="message">
                  Describe your issue
                </Label>

                <textarea
                  ref={textareaRef}
                  id="message"
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Please describe your issue in detail…"
                  autoFocus
                  style={{
                    minHeight: 120,
                    maxHeight: 400,
                    resize: 'none',
                    overflow: 'auto',
                  }}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                />

                {/* Writing guide */}
                <div className="rounded-lg border border-dashed bg-muted/40 px-4 py-3 space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
                    <Sparkles size={11} />
                    Tips for a great ticket — helps the AI give better results
                  </p>

                  <ul className="text-xs text-muted-foreground space-y-1 list-none pl-0">
                    <li className="flex items-start gap-1.5">
                      <span className="mt-0.5 shrink-0 text-primary">
                        1.
                      </span>
                      What happened? Describe the problem clearly.
                    </li>

                    <li className="flex items-start gap-1.5">
                      <span className="mt-0.5 shrink-0 text-primary">
                        2.
                      </span>
                      What did you expect to happen instead?
                    </li>

                    <li className="flex items-start gap-1.5">
                      <span className="mt-0.5 shrink-0 text-primary">
                        3.
                      </span>
                      Any error messages or steps to reproduce?
                    </li>
                  </ul>
                </div>

                {/* Character counter + progress bar */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                      {charCount} characters

                      {!isReady && (
                        <span className="ml-1 text-muted-foreground/70">
                          — {MIN_CHARS - charCount} more to enable submit
                        </span>
                      )}

                      {isReady && (
                        <span className="ml-1 text-green-600 dark:text-green-400">
                          — ready to submit
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="h-1 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${
                        isReady
                          ? 'bg-green-500'
                          : 'bg-primary/60'
                      }`}
                      style={{
                        width: `${progressPercent}%`,
                      }}
                    />
                  </div>

                  {!isReady && charCount > 0 && (
                    <p className="text-xs text-muted-foreground/70">
                      Add more detail for a better AI analysis.
                    </p>
                  )}
                </div>
              </div>

              {/* ── Error ─────────────────────────────────────────────────── */}
              {error && (
                <p className="text-sm text-destructive rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2">
                  {error}
                </p>
              )}

              {/* ── Actions ───────────────────────────────────────────────── */}
              <div className="flex gap-3">
                <Button
                  type="submit"
                  disabled={!isReady}
                  className="gap-2 transition-all"
                >
                  <Sparkles size={14} />
                  Submit Ticket
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleCancel}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
