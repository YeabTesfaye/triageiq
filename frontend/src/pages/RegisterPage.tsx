import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Eye, EyeOff } from 'lucide-react'

// Password strength helpers
function getPasswordStrength(password: string): number {
  if (!password) return 0
  let score = 0
  if (password.length >= 8) score++
  if (/[A-Z]/.test(password)) score++
  if (/[0-9]/.test(password)) score++
  if (/[^A-Za-z0-9]/.test(password)) score++
  return score // 0–4
}

const STRENGTH_LABELS = ['', 'Weak', 'Fair', 'Good', 'Strong']
const STRENGTH_COLORS = ['', '#ef4444', '#f97316', '#eab308', '#22c55e']

export default function RegisterPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '', full_name: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [passwordTouched, setPasswordTouched] = useState(false)

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }))

  const handlePasswordChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, password: e.target.value }))
    if (!passwordTouched) setPasswordTouched(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.post('/auth/register', form)
      const r = await api.post('/auth/login', { email: form.email, password: form.password })
      await login(r.data.access_token)
      navigate('/dashboard')
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const strength = getPasswordStrength(form.password)
  const strengthLabel = STRENGTH_LABELS[strength]
  const strengthColor = STRENGTH_COLORS[strength]

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full" style={{ maxWidth: '440px' }}>
        <CardHeader className="text-center pb-2">
          {/* Brand wordmark — mirrors the login screen */}
          <p
            style={{
              fontSize: '18px',
              fontWeight: 500,
              color: 'hsl(var(--foreground))',
              marginBottom: '4px',
              letterSpacing: '-0.01em',
            }}
          >
            TriageIQ
          </p>
          {/* Clear heading hierarchy */}
          <CardTitle style={{ fontSize: '28px', fontWeight: 600, lineHeight: 1.2 }}>
            Create account
          </CardTitle>
          <CardDescription style={{ fontSize: '14px', fontWeight: 400, marginTop: '8px' }}>
            Get started with TriageIQ
          </CardDescription>
        </CardHeader>

        <CardContent className="pt-4">
          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Full name */}
            <div className="space-y-1.5">
              <Label
                htmlFor="name"
                style={{ fontSize: '13px', fontWeight: 500 }}
              >
                Full name
              </Label>
              <Input
                id="name"
                placeholder="Jane Smith"
                value={form.full_name}
                onChange={set('full_name')}
                required
                autoFocus
              />
            </div>

            {/* Email */}
            <div className="space-y-1.5">
              <Label
                htmlFor="email"
                style={{ fontSize: '13px', fontWeight: 500 }}
              >
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={form.email}
                onChange={set('email')}
                required
              />
            </div>

            {/* Password with show/hide toggle + strength meter */}
            <div className="space-y-1.5">
              <Label
                htmlFor="password"
                style={{ fontSize: '13px', fontWeight: 500 }}
              >
                Password
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="8+ characters"
                  value={form.password}
                  onChange={handlePasswordChange}
                  required
                  style={{ paddingRight: '40px' }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  style={{
                    position: 'absolute',
                    right: '10px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '4px',
                    color: 'hsl(var(--muted-foreground))',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {/* Strength bar — only shown once user starts typing */}
              {passwordTouched && (
                <div style={{ marginTop: '6px' }}>
                  {/* 4-segment bar */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, 1fr)',
                      gap: '4px',
                      marginBottom: '6px',
                    }}
                  >
                    {[1, 2, 3, 4].map((seg) => (
                      <div
                        key={seg}
                        style={{
                          height: '3px',
                          borderRadius: '2px',
                          backgroundColor:
                            strength >= seg
                              ? strengthColor
                              : 'hsl(var(--border))',
                          transition: 'background-color 0.2s ease',
                        }}
                      />
                    ))}
                  </div>
                  {/* Requirement hints */}
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <p
                      style={{
                        fontSize: '12px',
                        color: 'hsl(var(--muted-foreground))',
                        margin: 0,
                      }}
                    >
                      Min. 8 characters · uppercase · number · symbol
                    </p>
                    {strengthLabel && (
                      <span
                        style={{
                          fontSize: '12px',
                          fontWeight: 500,
                          color: strengthColor,
                        }}
                      >
                        {strengthLabel}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Error message */}
            {error && (
              <p
                style={{
                  fontSize: '13px',
                  color: 'hsl(var(--destructive))',
                  margin: 0,
                }}
              >
                {error}
              </p>
            )}

            {/* CTA — accent colour for stronger contrast on dark theme */}
            <Button
              type="submit"
              className="w-full"
              disabled={loading}
              style={{
                backgroundColor: 'hsl(217 91% 60%)',   /* blue-500 equivalent */
                color: '#ffffff',
                fontWeight: 500,
                fontSize: '15px',
                height: '40px',
                border: 'none',
                cursor: loading ? 'not-allowed' : 'pointer',
                opacity: loading ? 0.7 : 1,
                transition: 'opacity 0.15s ease, background-color 0.15s ease',
              }}
            >
              {loading ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    style={{ animation: 'spin 0.8s linear infinite' }}
                  >
                    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                  </svg>
                  Creating account…
                </span>
              ) : (
                'Create account'
              )}
            </Button>

            <p
              className="text-center"
              style={{ fontSize: '14px', color: 'hsl(var(--muted-foreground))' }}
            >
              Already have an account?{' '}
              <Link
                to="/login"
                className="underline underline-offset-4 hover:text-primary"
              >
                Sign in
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>

      {/* Spinner keyframe */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}
