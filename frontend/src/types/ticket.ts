export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed'
export type TicketPriority = 'high' | 'medium' | 'low'
export type TicketCategory = 'billing' | 'technical' | 'general'

export interface Ticket {
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
