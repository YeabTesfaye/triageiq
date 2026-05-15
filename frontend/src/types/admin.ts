import type { TicketStatus, TicketPriority, TicketCategory } from './ticket'

export type UserRole   = 'superadmin' | 'admin' | 'moderator' | 'user'
export type UserStatus = 'active' | 'suspended' | 'banned'

export interface PaginationMeta {
  total: number
  limit: number
  offset: number
  has_next: boolean
  has_prev: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  meta: PaginationMeta
}

// mirrors AdminUserResponse
export interface AdminUser {
  id: string
  email: string
  full_name: string
  role: UserRole
  status: UserStatus
  is_verified: boolean
  last_login_at: string | null
  failed_login_attempts: number
  deleted_at: string | null
  created_at: string
  updated_at: string
}

// mirrors AdminTicketResponse
export interface AdminTicket {
  id: string
  user_id: string
  message: string
  category: TicketCategory | null
  priority: TicketPriority | null
  ai_response: string | null
  status: TicketStatus
  created_at: string
  updated_at: string
}

// mirrors AuditLogResponse
export interface AuditLog {
  id: string
  actor_id: string | null
  actor_role: UserRole
  action: string
  target_type: string
  target_id: string
  before_state: Record<string, unknown> | null
  after_state: Record<string, unknown> | null
  ip_address: string | null
  user_agent: string | null
  created_at: string
}
