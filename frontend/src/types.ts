export interface Role {
  id: number;
  name: string;
  description?: string | null;
}

export interface User {
  id: number;
  email: string;
  full_name?: string | null;
  role?: Role | null;
  primary_role?: Role | null;
  roles: Role[];
  created_at: string;
  is_active: boolean;
  archived_at?: string | null;
  archived_reason?: string | null;
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
  lot?: string | null;
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
  is_archived: boolean;
  archived_at?: string | null;
  archived_reason?: string | null;
  archived_by_user_id?: number | null;
  former_lot?: string | null;
  linked_users?: User[];
}

export interface Resident {
  user?: User | null;
  owner?: Owner | null;
}

export interface UserProfileUpdatePayload {
  full_name?: string | null;
  email?: string;
  current_password?: string;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

export interface OwnerSelfUpdatePayload {
  primary_name?: string | null;
  secondary_name?: string | null;
  property_address?: string | null;
  mailing_address?: string | null;
  primary_email?: string | null;
  secondary_email?: string | null;
  primary_phone?: string | null;
  secondary_phone?: string | null;
  emergency_contact?: string | null;
  notes?: string | null;
}

export interface OwnerArchivePayload {
  reason?: string;
}

export interface OwnerRestorePayload {
  reactivate_user?: boolean;
}

export interface OwnerUpdatePayload {
  primary_name?: string | null;
  secondary_name?: string | null;
  lot?: string | null;
  property_address?: string | null;
  mailing_address?: string | null;
  primary_email?: string | null;
  secondary_email?: string | null;
  primary_phone?: string | null;
  secondary_phone?: string | null;
  occupancy_status?: string | null;
  emergency_contact?: string | null;
  is_rental?: boolean | null;
  notes?: string | null;
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
  property_address?: string | null;
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

export type ViolationStatus =
  | 'NEW'
  | 'UNDER_REVIEW'
  | 'WARNING_SENT'
  | 'HEARING'
  | 'FINE_ACTIVE'
  | 'RESOLVED'
  | 'ARCHIVED';

export interface FineSchedule {
  id: number;
  name: string;
  description?: string | null;
  base_amount: string;
  escalation_amount?: string | null;
  escalation_days?: number | null;
  created_at: string;
  updated_at: string;
}

export interface ViolationNotice {
  id: number;
  violation_id: number;
  notice_type: string;
  template_key: string;
  subject: string;
  body: string;
  pdf_path?: string | null;
  created_at: string;
}

export interface Appeal {
  id: number;
  violation_id: number;
  submitted_by_owner_id: number;
  status: string;
  reason: string;
  decision_notes?: string | null;
  submitted_at: string;
  decided_at?: string | null;
  reviewed_by_user_id?: number | null;
}

export interface Violation {
  id: number;
  owner_id: number;
  reported_by_user_id: number;
  fine_schedule_id?: number | null;
  status: ViolationStatus;
  category: string;
  description?: string | null;
  location?: string | null;
  opened_at: string;
  updated_at: string;
  due_date?: string | null;
  hearing_date?: string | null;
  fine_amount?: string | null;
  resolution_notes?: string | null;
  owner: Owner;
  notices: ViolationNotice[];
  appeals: Appeal[];
}

export interface ViolationCreatePayload {
  owner_id?: number;
  user_id?: number;
  category: string;
  description?: string | null;
  location?: string | null;
  fine_schedule_id?: number | null;
  due_date?: string | null;
}

export type ARCStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'IN_REVIEW'
  | 'REVISION_REQUESTED'
  | 'APPROVED'
  | 'APPROVED_WITH_CONDITIONS'
  | 'DENIED'
  | 'COMPLETED'
  | 'ARCHIVED';

export interface ARCAttachment {
  id: number;
  arc_request_id: number;
  original_filename: string;
  stored_filename: string;
  content_type?: string | null;
  file_size?: number | null;
  uploaded_at: string;
}

export interface ARCCondition {
  id: number;
  arc_request_id: number;
  condition_type: 'COMMENT' | 'REQUIREMENT';
  text: string;
  status: 'OPEN' | 'RESOLVED';
  created_at: string;
  resolved_at?: string | null;
  created_by_user_id: number;
}

export interface ARCInspection {
  id: number;
  arc_request_id: number;
  inspector_user_id?: number | null;
  scheduled_date?: string | null;
  completed_at?: string | null;
  result?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ARCRequest {
  id: number;
  owner_id: number;
  submitted_by_user_id: number;
  reviewer_user_id?: number | null;
  title: string;
  project_type?: string | null;
  description?: string | null;
  status: ARCStatus;
  submitted_at?: string | null;
  decision_notes?: string | null;
  final_decision_at?: string | null;
  final_decision_by_user_id?: number | null;
  revision_requested_at?: string | null;
  completed_at?: string | null;
  archived_at?: string | null;
  created_at: string;
  updated_at: string;
  owner: Owner;
  attachments: ARCAttachment[];
  conditions: ARCCondition[];
  inspections: ARCInspection[];
}

export interface BankTransaction {
  id: number;
  reconciliation_id?: number | null;
  uploaded_by_user_id: number;
  transaction_date?: string | null;
  description?: string | null;
  reference?: string | null;
  amount: string;
  status: 'PENDING' | 'MATCHED' | 'UNMATCHED';
  matched_payment_id?: number | null;
  matched_invoice_id?: number | null;
  source_file?: string | null;
  uploaded_at: string;
}

export interface Reconciliation {
  id: number;
  statement_date?: string | null;
  created_by_user_id: number;
  note?: string | null;
  total_transactions: number;
  matched_transactions: number;
  unmatched_transactions: number;
  matched_amount: string;
  unmatched_amount: string;
  created_at: string;
  transactions: BankTransaction[];
}

export interface BankImportSummary {
  reconciliation: Reconciliation;
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
