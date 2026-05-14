import { useState } from 'react'
import { useAuth } from '@/context/AuthContext'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { CheckCircle, AlertCircle } from 'lucide-react'

function Alert({ type, message }: { type: 'success' | 'error'; message: string }) {
  const Icon = type === 'success' ? CheckCircle : AlertCircle
  return (
    <div className={`flex items-center gap-2 text-sm p-3 rounded-lg border ${
      type === 'success'
        ? 'text-green-700 bg-green-50 border-green-200 dark:text-green-400 dark:bg-green-950 dark:border-green-800'
        : 'text-destructive bg-destructive/10 border-destructive/20'
    }`}>
      <Icon size={14} className="shrink-0" />
      {message}
    </div>
  )
}

export default function ProfilePage() {
  const { user, login, token } = useAuth()

  const initials = user?.full_name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2) ?? '?'

  const [name, setName] = useState(user?.full_name ?? '')
  const [nameStatus, setNameStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [nameSaving, setNameSaving] = useState(false)

  const [passwords, setPasswords] = useState({ current: '', next: '', confirm: '' })
  const [pwStatus, setPwStatus] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [pwSaving, setPwSaving] = useState(false)

  const saveName = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || name === user?.full_name) return
    setNameSaving(true)
    setNameStatus(null)
    try {
      await api.patch('/auth/me', { full_name: name.trim() })
      if (token) await login(token)
      setNameStatus({ type: 'success', msg: 'Name updated successfully.' })
    } catch {
      setNameStatus({ type: 'error', msg: 'Failed to update name.' })
    } finally {
      setNameSaving(false)
    }
  }

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
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setPwStatus({ type: 'error', msg: e.response?.data?.detail ?? 'Failed to change password.' })
    } finally {
      setPwSaving(false)
    }
  }

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground mt-1">Manage your account settings</p>
      </div>

      {/* Identity card */}
      <Card>
        <CardContent className="pt-6 flex items-center gap-4">
          <Avatar className="h-16 w-16">
            <AvatarFallback className="text-xl bg-primary text-primary-foreground font-semibold">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div>
            <p className="font-semibold text-lg">{user?.full_name}</p>
            <p className="text-sm text-muted-foreground">{user?.email}</p>
            <div className="flex items-center gap-2 mt-1.5">
              <Badge variant="outline" className="capitalize text-xs">{user?.role}</Badge>
              <Badge variant={user?.status === 'active' ? 'default' : 'destructive'} className="capitalize text-xs">
                {user?.status}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Edit name */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Display Name</CardTitle>
          <CardDescription>Update your full name</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={saveName} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Full name</Label>
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
            >
              {nameSaving ? 'Saving…' : 'Save name'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Separator />

      {/* Change password */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Change Password</CardTitle>
          <CardDescription>Use a strong password of at least 8 characters</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={savePassword} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="current">Current password</Label>
              <Input
                id="current"
                type="password"
                value={passwords.current}
                onChange={(e) => setPasswords((p) => ({ ...p, current: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="new">New password</Label>
              <Input
                id="new"
                type="password"
                value={passwords.next}
                onChange={(e) => setPasswords((p) => ({ ...p, next: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm">Confirm new password</Label>
              <Input
                id="confirm"
                type="password"
                value={passwords.confirm}
                onChange={(e) => setPasswords((p) => ({ ...p, confirm: e.target.value }))}
                required
              />
            </div>
            {pwStatus && <Alert type={pwStatus.type} message={pwStatus.msg} />}
            <Button type="submit" size="sm" disabled={pwSaving}>
              {pwSaving ? 'Changing…' : 'Change password'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
