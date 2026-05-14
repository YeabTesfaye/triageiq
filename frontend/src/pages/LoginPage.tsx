import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Eye, EyeOff } from 'lucide-react'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const r = await api.post('/auth/login', { email, password })
      await login(r.data.access_token)
      navigate('/dashboard')
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } } }
      setError(e.response?.data?.detail || 'Incorrect email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <Card className="w-full" style={{ maxWidth: '440px' }}>
        <CardHeader className="text-center pb-2">
          <CardTitle
            style={{ fontSize: '28px', fontWeight: 600, lineHeight: 1.2, letterSpacing: '-0.01em' }}
          >
            TriageIQ
          </CardTitle>
          <CardDescription style={{ fontSize: '14px', fontWeight: 400, marginTop: '8px' }}>
            Sign in to your account
          </CardDescription>
        </CardHeader>

        <CardContent className="pt-4">
          <form onSubmit={handleSubmit} className="space-y-4">

            {/* Email */}
            <div className="space-y-1.5">
              <Label htmlFor="email" style={{ fontSize: '13px', fontWeight: 500 }}>
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                // Error state: red border when error is present
                style={
                  error
                    ? {
                        borderColor: 'hsl(var(--destructive))',
                        boxShadow: '0 0 0 3px hsla(var(--destructive), 0.15)',
                      }
                    : undefined
                }
              />
            </div>

            {/* Password with forgot link + show/hide toggle */}
            <div className="space-y-1.5">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Label htmlFor="password" style={{ fontSize: '13px', fontWeight: 500 }}>
                  Password
                </Label>
                {/* Forgot password — right-aligned, inline with label */}
                <Link
                  to="/forgot-password"
                  style={{
                    fontSize: '12px',
                    color: 'hsl(var(--muted-foreground))',
                    textDecoration: 'underline',
                    textUnderlineOffset: '3px',
                    lineHeight: 1,
                  }}
                  className="hover:text-primary"
                >
                  Forgot password?
                </Link>
              </div>

              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  style={{
                    paddingRight: '40px',
                    ...(error
                      ? {
                          borderColor: 'hsl(var(--destructive))',
                          boxShadow: '0 0 0 3px hsla(var(--destructive), 0.15)',
                        }
                      : undefined),
                  }}
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
            </div>

            {/* Error banner — shown below fields, not inside them */}
            {error && (
              <div
                role="alert"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  backgroundColor: 'hsl(var(--destructive) / 0.08)',
                  border: '1px solid hsl(var(--destructive) / 0.25)',
                  fontSize: '13px',
                  color: 'hsl(var(--destructive))',
                }}
              >
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                  style={{ flexShrink: 0 }}
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {error}
              </div>
            )}

            {/* CTA */}
            <Button
              type="submit"
              className="w-full"
              disabled={loading}
              style={{
                backgroundColor: 'hsl(217 91% 60%)',
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
                  Signing in…
                </span>
              ) : (
                'Sign in'
              )}
            </Button>

            <p
              className="text-center"
              style={{ fontSize: '14px', color: 'hsl(var(--muted-foreground))' }}
            >
              No account?{' '}
              <Link to="/register" className="underline underline-offset-4 hover:text-primary">
                Register
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        #email:focus,
        #password:focus {
          outline: none;
          border-color: #3B82F6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
        }
      `}</style>
    </div>
  )
}
