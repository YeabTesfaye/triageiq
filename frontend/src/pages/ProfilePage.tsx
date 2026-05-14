import { useState, useRef } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { CheckCircle, AlertCircle, Camera, Check } from 'lucide-react'

// ─── Alert banner ────────────────────────────────────────────────────────────
function Alert({ type, message }: { type: 'success' | 'error'; message: string }) {
  const Icon = type === 'success' ? CheckCircle : AlertCircle
  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '10px 12px',
        borderRadius: '8px',
        fontSize: '13px',
        backgroundColor:
          type === 'success'
            ? 'hsl(142 76% 36% / 0.08)'
            : 'hsl(var(--destructive) / 0.08)',
        border: `1px solid ${
          type === 'success'
            ? 'hsl(142 76% 36% / 0.25)'
            : 'hsl(var(--destructive) / 0.25)'
        }`,
        color:
          type === 'success'
            ? 'hsl(142 76% 36%)'
            : 'hsl(var(--destructive))',
      }}
    >
      <Icon size={14} style={{ flexShrink: 0 }} />
      {message}
    </div>
  )
}

// ─── Section heading with brand left-border accent ───────────────────────────
function SectionHeader({
  title,
  description,
}: {
  title: string
  description: string
}) {
  return (
    <div
      style={{
        borderLeft: '3px solid hsl(217 91% 60%)',
        paddingLeft: '12px',
        marginBottom: '4px',
      }}
    >
      <p style={{ fontSize: '15px', fontWeight: 600, margin: 0, lineHeight: 1.3 }}>
        {title}
      </p>
      <p
        style={{
          fontSize: '13px',
          color: 'hsl(var(--muted-foreground))',
          margin: '2px 0 0',
        }}
      >
        {description}
      </p>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function ProfilePage() {
  const { user, login, token } = useAuth()

  const initials =
    user?.full_name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2) ?? '?'

  // Avatar upload
  const [avatarSrc, setAvatarSrc] = useState<string | undefined>(undefined)
  const [avatarHovered, setAvatarHovered] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => setAvatarSrc(ev.target?.result as string)
    reader.readAsDataURL(file)
  }

  // Display name
  const [name, setName] = useState(user?.full_name ?? '')
  const [nameStatus, setNameStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [nameSaving, setNameSaving] = useState(false)
  const [nameSaved, setNameSaved] = useState(false)

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || name === user?.full_name) return
    setNameSaving(true)
    setNameStatus(null)
    try {
      await api.patch('/auth/me', { full_name: name.trim() })
      if (token) await login(token)
      setNameStatus({ type: 'success', msg: 'Name updated successfully.' })
      // Inline button feedback
      setNameSaved(true)
      setTimeout(() => setNameSaved(false), 2000)
    } catch {
      setNameStatus({ type: 'error', msg: 'Failed to update name.' })
    } finally {
      setNameSaving(false)
    }
  }

  // Password
  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
  const [pwStatus, setPwStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [pwSaving, setPwSaving] = useState(false)
  const [pwSaved, setPwSaved] = useState(false)

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (passwords.next !== passwords.confirm) {
      setPwStatus({ type: 'error', msg: 'New passwords do not match.' })
      return
    }
    if (passwords.next.length < 8) {
      setPwStatus({ type: 'error', msg: 'Password must be at least 8 characters.' })
      return
    }
    setPwSaving(true)
    setPwStatus(null)
    try {
      await api.patch('/auth/me/password', {
        current_password: passwords.current,
        new_password: passwords.next,
      })
      setPasswords({ current: '', next: '', confirm: '' })
      setPwStatus({ type: 'success', msg: 'Password changed successfully.' })
      setPwSaved(true)
      setTimeout(() => setPwSaved(false), 2000)
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setPwStatus({ type: 'error', msg: e.response?.data?.detail ?? 'Failed to change password.' })
    } finally {
      setPwSaving(false)
    }
  }

  const labelStyle: React.CSSProperties = { fontSize: '13px', fontWeight: 500 }

  return (
    <div style={{ maxWidth: '560px', display: 'flex', flexDirection: 'column', gap: '24px' }}>

      {/* Page heading */}
      <div>
        <h1 style={{ fontSize: '22px', fontWeight: 600, letterSpacing: '-0.01em', margin: 0 }}>
          Profile
        </h1>
        <p style={{ fontSize: '14px', color: 'hsl(var(--muted-foreground))', margin: '4px 0 0' }}>
          Manage your account settings
        </p>
      </div>

      {/* ── Identity card ── */}
      <Card>
        <CardContent style={{ paddingTop: '24px', paddingBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>

            {/* Avatar with hover upload affordance */}
            <div
              style={{ position: 'relative', flexShrink: 0, cursor: 'pointer' }}
              onMouseEnter={() => setAvatarHovered(true)}
              onMouseLeave={() => setAvatarHovered(false)}
              onClick={() => fileInputRef.current?.click()}
              title="Upload photo"
            >
              {/* Outer ring */}
              <div
                style={{
                  padding: '2px',
                  borderRadius: '50%',
                  border: '2px solid hsl(var(--border))',
                  display: 'inline-flex',
                }}
              >
                <Avatar style={{ width: '72px', height: '72px' }}>
                  {avatarSrc && <AvatarImage src={avatarSrc} alt={user?.full_name} />}
                  <AvatarFallback
                    style={{
                      fontSize: '22px',
                      fontWeight: 600,
                      background: 'hsl(217 91% 60%)',
                      color: '#fff',
                      width: '72px',
                      height: '72px',
                    }}
                  >
                    {initials}
                  </AvatarFallback>
                </Avatar>
              </div>

              {/* Camera overlay on hover */}
              <div
                aria-hidden="true"
                style={{
                  position: 'absolute',
                  inset: 0,
                  borderRadius: '50%',
                  background: 'rgba(0,0,0,0.45)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: avatarHovered ? 1 : 0,
                  transition: 'opacity 0.15s ease',
                }}
              >
                <Camera size={20} color="#fff" />
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={handleAvatarChange}
                aria-label="Upload profile photo"
              />
            </div>

            {/* User info */}
            <div>
              <p style={{ fontWeight: 600, fontSize: '17px', margin: 0 }}>{user?.full_name}</p>
              <p style={{ fontSize: '13px', color: 'hsl(var(--muted-foreground))', margin: '2px 0 8px' }}>
                {user?.email}
              </p>

              {/* Consistent badge row */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                {/* Role badge — muted pill */}
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 500,
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background: 'hsl(var(--muted))',
                    color: 'hsl(var(--muted-foreground))',
                    textTransform: 'capitalize',
                  }}
                >
                  {user?.role}
                </span>

                {/* Status badge — green dot + label */}
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 500,
                    padding: '2px 8px',
                    borderRadius: '999px',
                    background:
                      user?.status === 'active'
                        ? 'hsl(142 76% 36% / 0.1)'
                        : 'hsl(var(--destructive) / 0.1)',
                    color:
                      user?.status === 'active'
                        ? 'hsl(142 76% 36%)'
                        : 'hsl(var(--destructive))',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    textTransform: 'capitalize',
                  }}
                >
                  <span
                    style={{
                      width: '6px',
                      height: '6px',
                      borderRadius: '50%',
                      background:
                        user?.status === 'active'
                          ? 'hsl(142 76% 36%)'
                          : 'hsl(var(--destructive))',
                      flexShrink: 0,
                    }}
                  />
                  {user?.status}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Display name ── */}
      <Card>
        <CardHeader style={{ paddingBottom: '16px' }}>
          <SectionHeader title="Display Name" description="Update your full name" />
        </CardHeader>
        <CardContent>
          <form onSubmit={saveName} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <Label htmlFor="name" style={labelStyle}>Full name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your full name"
              />
            </div>

            {nameStatus && <Alert type={nameStatus.type} message={nameStatus.msg} />}

            <Button
              type="submit"
              size="sm"
              disabled={nameSaving || !name.trim() || name === user?.full_name}
              style={{
                alignSelf: 'flex-start',
                backgroundColor: nameSaved ? 'hsl(142 76% 36%)' : 'hsl(217 91% 60%)',
                color: '#fff',
                border: 'none',
                fontWeight: 500,
                fontSize: '13px',
                minWidth: '96px',
                transition: 'background-color 0.2s ease',
                opacity: nameSaving || (!name.trim() || name === user?.full_name) ? 0.6 : 1,
              }}
            >
              {nameSaving ? (
                'Saving…'
              ) : nameSaved ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Check size={13} /> Saved
                </span>
              ) : (
                'Save name'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* ── Change password ── */}
      <Card>
        <CardHeader style={{ paddingBottom: '16px' }}>
          <SectionHeader
            title="Change Password"
            description="Use a strong password of at least 8 characters"
          />
        </CardHeader>
        <CardContent>
          <form onSubmit={savePassword} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <Label htmlFor="current" style={labelStyle}>Current password</Label>
              <Input
                id="current"
                type="password"
                value={passwords.current}
                onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))}
                required
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <Label htmlFor="new" style={labelStyle}>New password</Label>
              <Input
                id="new"
                type="password"
                value={passwords.next}
                onChange={(e) => setPasswords((p) => ({ ...p, next: e.target.value }))}
                required
              />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <Label htmlFor="confirm" style={labelStyle}>Confirm new password</Label>
              <Input
                id="confirm"
                type="password"
                value={passwords.confirm}
                onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
                required
              />
            </div>

            {pwStatus && <Alert type={pwStatus.type} message={pwStatus.msg} />}

            <Button
              type="submit"
              size="sm"
              disabled={pwSaving}
              style={{
                alignSelf: 'flex-start',
                backgroundColor: pwSaved ? 'hsl(142 76% 36%)' : 'hsl(217 91% 60%)',
                color: '#fff',
                border: 'none',
                fontWeight: 500,
                fontSize: '13px',
                minWidth: '128px',
                transition: 'background-color 0.2s ease',
                opacity: pwSaving ? 0.6 : 1,
              }}
            >
              {pwSaving ? (
                'Changing…'
              ) : pwSaved ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                  <Check size={13} /> Changed
                </span>
              ) : (
                'Change password'
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

    </div>
  )
}
