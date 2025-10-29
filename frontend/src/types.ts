export interface Role {
  id: number;
  name: string;
  description?: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name?: string | null;
  role: Role;
  created_at: string;
}

export interface Invoice {
  id: number;
  owner_id: number;
  lot?: string | null;
  amount: string;
  original_amount: string;
  late_fee_total: string;
  due_date: string;
  status: string;
  late_fee_applied: boolean;
  notes?: string | null;
  last_late_fee_applied_at?: string | null;
  last_reminder_sent_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Payment {
  id: number;
  owner_id: number;
  invoice_id?: number | null;
  amount: string;
  date_received: string;
  method?: string | null;
  reference?: string | null;
  notes?: string | null;
}

export interface LedgerEntry {
  id: number;
  owner_id: number;
  entry_type: string;
  amount: string;
  balance_after?: string | null;
  description?: string | null;
  timestamp: string;
}

export interface Owner {
  id: number;
  primary_name: string;
  secondary_name?: string | null;
  lot: string;
  property_address: string;
  mailing_address?: string | null;
  primary_email?: string | null;
  secondary_email?: string | null;
  primary_phone?: string | null;
  secondary_phone?: string | null;
  occupancy_status?: string | null;
  emergency_contact?: string | null;
  is_rental?: boolean;
  lease_document_path?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Contract {
  id: number;
  vendor_name: string;
  service_type?: string | null;
  start_date: string;
  end_date?: string | null;
  auto_renew: boolean;
  termination_notice_deadline?: string | null;
  file_path?: string | null;
  value?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Announcement {
  id: number;
  subject: string;
  body: string;
  created_at: string;
  created_by_user_id: number;
  delivery_methods: string[];
  pdf_path?: string | null;
}

export interface EmailBroadcastRecipient {
  owner_id?: number | null;
  owner_name?: string | null;
  lot?: string | null;
  email: string;
  contact_type?: string | null;
}

export interface EmailBroadcast {
  id: number;
  subject: string;
  body: string;
  segment: string;
  recipients: EmailBroadcastRecipient[];
  recipient_count: number;
  created_at: string;
  created_by_user_id: number;
}

export interface EmailBroadcastSegment {
  key: string;
  label: string;
  description: string;
  recipient_count: number;
}

export interface Reminder {
  id: number;
  reminder_type: string;
  title: string;
  description?: string | null;
  entity_type: string;
  entity_id: number;
  due_date?: string | null;
  context?: Record<string, unknown> | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface BillingSummary {
  total_balance: string;
  open_invoices: number;
  owner_count: number;
}

export interface LateFeeTier {
  id: number;
  sequence_order: number;
  trigger_days_after_grace: number;
  fee_type: 'flat' | 'percent';
  fee_amount: string;
  fee_percent: number;
  description?: string | null;
}

export interface BillingPolicy {
  name: string;
  grace_period_days: number;
  dunning_schedule_days: number[];
  tiers: LateFeeTier[];
}

export interface RoleOption {
  id: number;
  name: string;
  description?: string | null;
}

export interface LateFeeTierInput {
  id?: number;
  sequence_order: number;
  trigger_days_after_grace: number;
  fee_type: 'flat' | 'percent';
  fee_amount?: string;
  fee_percent?: number;
  description?: string | null;
}

export interface BillingPolicyUpdatePayload {
  grace_period_days: number;
  dunning_schedule_days: number[];
  tiers: LateFeeTierInput[];
}
