import {
  Announcement,
  CommunicationMessage,
  Appeal,
  ARCCondition,
  ARCInspection,
  ARCRequest,
  ARCAttachment,
  BankImportSummary,
  BankTransaction,
  BillingPolicy,
  BillingPolicyUpdatePayload,
  BillingSummary,
  Contract,
  ElectionAdminBallot,
  ElectionCandidate,
  ElectionDetail,
  ElectionListItem,
  ElectionStats,
  ElectionPublicDetail,
  EmailBroadcast,
  EmailBroadcastSegment,
  FineSchedule,
  ForwardAttorneyResponse,
  Invoice,
  Notification,
  AutopayEnrollment,
  AutopayAmountType,
  LoginBackgroundResponse,
  Owner,
  OwnerSelfUpdatePayload,
  OwnerArchivePayload,
  OwnerRestorePayload,
  OwnerUpdatePayload,
  OverdueAccount,
  OverdueContactResponse,
  BudgetSummary,
  BudgetDetail,
  BudgetLineItem,
  ReservePlanItem,
  BudgetAttachment,
  DocumentFolder,
  DocumentTreeResponse,
  GovernanceDocument,
  Meeting,
  PaperworkItem,
  PaperworkFeatures,
  Reminder,
  Reconciliation,
  Role,
  RoleOption,
  Resident,
  PasswordChangePayload,
  Template,
  TemplateMergeTag,
  User,
  UserProfileUpdatePayload,
  Violation,
  ViolationCreatePayload,
  ViolationNotice,
  ViolationMessage,
  TwoFactorSetupResponse,
  AuditLogResponse,
  VendorPayment,
} from '../types';
import { api, publicApi, API_BASE_URL, setAuthToken } from '../lib/api/client';

export { API_BASE_URL, setAuthToken };

export const fetchLoginBackground = async (): Promise<LoginBackgroundResponse> => {
  const { data } = await publicApi.get<LoginBackgroundResponse>('/system/login-background');
  return data;
};

export const uploadLoginBackground = async (file: File): Promise<LoginBackgroundResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<LoginBackgroundResponse>('/system/login-background', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const createPaymentSession = async (invoiceId: number): Promise<{ checkoutUrl: string }> => {
  const { data } = await api.post<{ checkoutUrl: string }>('/payments/session', {
    invoiceId,
  });
  return data;
};

export interface AutopayEnrollmentPayload {
  payment_day: number;
  amount_type: AutopayAmountType;
  fixed_amount?: string;
  owner_id?: number;
}

export const fetchAutopayEnrollment = async (ownerId?: number): Promise<AutopayEnrollment> => {
  const params = ownerId ? `?owner_id=${ownerId}` : '';
  const { data } = await api.get<AutopayEnrollment>(`/payments/autopay${params}`);
  return data;
};

export const upsertAutopayEnrollment = async (payload: AutopayEnrollmentPayload): Promise<AutopayEnrollment> => {
  const { data } = await api.post<AutopayEnrollment>('/payments/autopay', payload);
  return data;
};

export const cancelAutopay = async (ownerId?: number): Promise<AutopayEnrollment> => {
  const params = ownerId ? `?owner_id=${ownerId}` : '';
  const { data } = await api.delete<AutopayEnrollment>(`/payments/autopay${params}`);
  return data;
};

export const fetchVendorPayments = async (): Promise<VendorPayment[]> => {
  const { data } = await api.get<VendorPayment[]>('/payments/vendors');
  return data;
};

export const createVendorPaymentRequest = async (payload: {
  contract_id?: number | null;
  vendor_name?: string;
  amount: string;
  payment_method: 'ACH' | 'CHECK' | 'WIRE' | 'CARD' | 'CASH' | 'OTHER';
  check_number?: string;
  notes?: string;
}): Promise<VendorPayment> => {
  const { data } = await api.post<VendorPayment>('/payments/vendors', payload);
  return data;
};

export const sendVendorPayment = async (paymentId: number): Promise<VendorPayment> => {
  const { data } = await api.post<VendorPayment>(`/payments/vendors/${paymentId}/send`);
  return data;
};

export const markVendorPaymentPaid = async (paymentId: number): Promise<VendorPayment> => {
  const { data } = await api.post<VendorPayment>(`/payments/vendors/${paymentId}/mark-paid`);
  return data;
};

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  roles: string[];
  primary_role?: string | null;
  expires_in: number;
  refresh_expires_in: number;
}

export const login = async (email: string, password: string, otp?: string): Promise<LoginResponse> => {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  if (otp) {
    params.append('otp', otp);
  }
  const { data } = await api.post<LoginResponse>('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
};

export const refreshSession = async (payload: { refresh_token: string }): Promise<LoginResponse> => {
  const { data } = await api.post<LoginResponse>('/auth/refresh', payload);
  return data;
};

export const fetchCurrentUser = async (): Promise<User> => {
  const { data } = await api.get<User>('/auth/me');
  return data;
};

export const fetchInvoices = async (): Promise<Invoice[]> => {
  const { data } = await api.get<Invoice[]>('/billing/invoices');
  return data;
};

export const fetchBillingSummary = async (): Promise<BillingSummary> => {
  const { data } = await api.get<BillingSummary>('/billing/summary');
  return data;
};

export const fetchOverdueAccounts = async (): Promise<OverdueAccount[]> => {
  const { data } = await api.get<OverdueAccount[]>('/billing/overdue');
  return data;
};

export const contactOverdueOwner = async (
  ownerId: number,
  message?: string,
): Promise<OverdueContactResponse> => {
  const payload = message ? { message } : {};
  const { data } = await api.post<OverdueContactResponse>(`/billing/overdue/${ownerId}/contact`, payload);
  return data;
};

export const forwardOverdueToAttorney = async (
  ownerId: number,
  notes?: string,
): Promise<ForwardAttorneyResponse> => {
  const payload = notes ? { notes } : {};
  const { data } = await api.post<ForwardAttorneyResponse>(
    `/billing/overdue/${ownerId}/forward-attorney`,
    payload,
  );
  return data;
};

export const fetchBudgets = async (): Promise<BudgetSummary[]> => {
  const { data } = await api.get<BudgetSummary[]>('/budgets/');
  return data;
};

export const createBudget = async (payload: { year: number; home_count?: number; notes?: string }): Promise<BudgetDetail> => {
  const { data } = await api.post<BudgetDetail>('/budgets/', payload);
  return data;
};

export const updateBudget = async (budgetId: number, payload: { home_count?: number; notes?: string }): Promise<BudgetDetail> => {
  const { data } = await api.patch<BudgetDetail>(`/budgets/${budgetId}`, payload);
  return data;
};

export const fetchBudgetDetail = async (budgetId: number): Promise<BudgetDetail> => {
  const { data } = await api.get<BudgetDetail>(`/budgets/${budgetId}`);
  return data;
};

export const addBudgetLineItem = async (
  budgetId: number,
  payload: { label: string; category?: string; amount: string; is_reserve?: boolean; sort_order?: number },
): Promise<BudgetLineItem> => {
  const { data } = await api.post<BudgetLineItem>(`/budgets/${budgetId}/line-items`, payload);
  return data;
};

export const updateBudgetLineItem = async (
  itemId: number,
  payload: { label?: string; category?: string; amount?: string; is_reserve?: boolean; sort_order?: number },
): Promise<BudgetLineItem> => {
  const { data } = await api.patch<BudgetLineItem>(`/budgets/line-items/${itemId}`, payload);
  return data;
};

export const deleteBudgetLineItem = async (itemId: number): Promise<void> => {
  await api.delete(`/budgets/line-items/${itemId}`);
};

export const addReserveItem = async (
  budgetId: number,
  payload: { name: string; target_year: number; estimated_cost: string; inflation_rate?: number; current_funding?: string; notes?: string },
): Promise<ReservePlanItem> => {
  const { data } = await api.post<ReservePlanItem>(`/budgets/${budgetId}/reserve-items`, payload);
  return data;
};

export const updateReserveItem = async (
  itemId: number,
  payload: Partial<{ name: string; target_year: number; estimated_cost: string; inflation_rate: number; current_funding: string; notes: string }>,
): Promise<ReservePlanItem> => {
  const { data } = await api.patch<ReservePlanItem>(`/budgets/reserve-items/${itemId}`, payload);
  return data;
};

export const deleteReserveItem = async (itemId: number): Promise<void> => {
  await api.delete(`/budgets/reserve-items/${itemId}`);
};

export const lockBudget = async (budgetId: number): Promise<BudgetDetail> => {
  const { data } = await api.post<BudgetDetail>(`/budgets/${budgetId}/lock`);
  return data;
};

export const uploadBudgetAttachment = async (budgetId: number, file: File): Promise<BudgetAttachment> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<BudgetAttachment>(`/budgets/${budgetId}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const deleteBudgetAttachment = async (attachmentId: number): Promise<void> => {
  await api.delete(`/budgets/attachments/${attachmentId}`);
};

export const approveBudget = async (budgetId: number): Promise<BudgetDetail> => {
  const { data } = await api.post<BudgetDetail>(`/budgets/${budgetId}/approve`);
  return data;
};

export const revokeBudgetApproval = async (budgetId: number): Promise<BudgetDetail> => {
  const { data } = await api.delete<BudgetDetail>(`/budgets/${budgetId}/approve`);
  return data;
};

export const unlockBudget = async (budgetId: number): Promise<BudgetDetail> => {
  const { data } = await api.post<BudgetDetail>(`/budgets/${budgetId}/unlock`);
  return data;
};

export const fetchPaperwork = async (options: { status?: string; requiredOnly?: boolean } = {}): Promise<PaperworkItem[]> => {
  const params = new URLSearchParams();
  if (options.status) params.append('status', options.status);
  if (options.requiredOnly) params.append('requiredOnly', 'true');
  const url = params.toString() ? `/paperwork?${params.toString()}` : '/paperwork';
  const { data } = await api.get<PaperworkItem[]>(url);
  return data;
};

export const fetchPaperworkFeatures = async (): Promise<PaperworkFeatures> => {
  const { data } = await api.get<PaperworkFeatures>('/paperwork/features');
  return data;
};

export const claimPaperworkItem = async (paperworkId: number): Promise<PaperworkItem> => {
  const { data } = await api.post<PaperworkItem>(`/paperwork/${paperworkId}/claim`);
  return data;
};

export const mailPaperworkItem = async (paperworkId: number): Promise<PaperworkItem> => {
  const { data } = await api.post<PaperworkItem>(`/paperwork/${paperworkId}/mail`);
  return data;
};

export const dispatchPaperwork = async (
  paperworkId: number,
  payload: { delivery_method: string },
): Promise<PaperworkItem> => {
  const { data } = await api.post<PaperworkItem>(`/paperwork/${paperworkId}/dispatch`, payload);
  return data;
};

export const getPaperworkPrintUrl = (paperworkId: number): string => `${API_BASE_URL}/paperwork/${paperworkId}/print`;
export const getPaperworkDownloadUrl = (paperworkId: number): string => `${API_BASE_URL}/paperwork/${paperworkId}/download`;

export const fetchDocumentTree = async (): Promise<DocumentTreeResponse> => {
  const { data } = await api.get<DocumentTreeResponse>('/documents');
  return data;
};

export const createDocumentFolder = async (payload: {
  name: string;
  description?: string;
  parent_id?: number | null;
}): Promise<DocumentFolder> => {
  const { data } = await api.post<DocumentFolder>('/documents/folders', payload);
  return data;
};

export const updateDocumentFolder = async (
  folderId: number,
  payload: { name?: string; description?: string | null; parent_id?: number | null },
): Promise<DocumentFolder> => {
  const { data } = await api.patch<DocumentFolder>(`/documents/folders/${folderId}`, payload);
  return data;
};

export const deleteDocumentFolder = async (folderId: number): Promise<void> => {
  await api.delete(`/documents/folders/${folderId}`);
};

export const uploadGovernanceDocument = async (payload: {
  folder_id?: number | null;
  title: string;
  description?: string;
  file: File;
}): Promise<GovernanceDocument> => {
  const formData = new FormData();
  formData.append('title', payload.title);
  if (payload.description) formData.append('description', payload.description);
  if (payload.folder_id != null) formData.append('folder_id', String(payload.folder_id));
  formData.append('file', payload.file);
  const { data } = await api.post<{ document: GovernanceDocument }>('/documents/files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data.document;
};

export const deleteGovernanceDocument = async (documentId: number): Promise<void> => {
  await api.delete(`/documents/files/${documentId}`);
};

export const getGovernanceDocumentDownloadUrl = (documentId: number): string =>
  `${API_BASE_URL}/documents/files/${documentId}/download`;

export const fetchMeetings = async (includePast = true): Promise<Meeting[]> => {
  const params = new URLSearchParams();
  if (!includePast) params.append('include_past', 'false');
  const url = params.toString() ? `/meetings?${params.toString()}` : '/meetings';
  const { data } = await api.get<Meeting[]>(url);
  return data;
};

export const createMeeting = async (payload: {
  title: string;
  description?: string;
  start_time: string;
  end_time?: string | null;
  location?: string | null;
  zoom_link?: string | null;
}): Promise<Meeting> => {
  const { data } = await api.post<Meeting>('/meetings', payload);
  return data;
};

export const updateMeeting = async (
  meetingId: number,
  payload: Partial<{
    title: string;
    description: string | null;
    start_time: string;
    end_time: string | null;
    location: string | null;
    zoom_link: string | null;
  }>,
): Promise<Meeting> => {
  const { data } = await api.patch<Meeting>(`/meetings/${meetingId}`, payload);
  return data;
};

export const deleteMeeting = async (meetingId: number): Promise<void> => {
  await api.delete(`/meetings/${meetingId}`);
};

export const uploadMeetingMinutes = async (meetingId: number, file: File): Promise<Meeting> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<Meeting>(`/meetings/${meetingId}/minutes`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const getMeetingMinutesDownloadUrl = (meetingId: number): string =>
  `${API_BASE_URL}/meetings/${meetingId}/minutes`;

export const fetchAuditLogs = async (options: { limit?: number; offset?: number } = {}): Promise<AuditLogResponse> => {
  const params = new URLSearchParams();
  if (options.limit) params.append('limit', String(options.limit));
  if (options.offset) params.append('offset', String(options.offset));
  const url = params.toString() ? `/audit-logs?${params.toString()}` : '/audit-logs';
  const { data } = await api.get<AuditLogResponse>(url);
  return data;
};

export const fetchBillingPolicy = async (): Promise<BillingPolicy> => {
  const { data } = await api.get<BillingPolicy>('/billing/policy');
  return data;
};

export const updateBillingPolicy = async (payload: BillingPolicyUpdatePayload): Promise<BillingPolicy> => {
  const { data } = await api.put<BillingPolicy>('/billing/policy', payload);
  return data;
};

export const fetchContracts = async (): Promise<Contract[]> => {
  const { data } = await api.get<Contract[]>('/contracts/');
  return data;
};

export const submitElectionVote = async (
  electionId: number,
  payload: { candidate_id?: number; write_in?: string },
): Promise<{ message: string }> => {
  const { data } = await api.post<{ message: string }>(`/elections/${electionId}/vote`, payload);
  return data;
};

export const fetchOwners = async (options: { includeArchived?: boolean } = {}): Promise<Owner[]> => {
  const params = new URLSearchParams();
  if (options.includeArchived) {
    params.append('include_archived', 'true');
  }
  const query = params.toString();
  const url = query ? `/owners/?${query}` : '/owners/';
  const { data } = await api.get<Owner[]>(url);
  return data;
};

export const fetchResidents = async (options: { includeArchived?: boolean } = {}): Promise<Resident[]> => {
  const params = new URLSearchParams();
  if (options.includeArchived) {
    params.append('include_archived', 'true');
  }
  const query = params.toString();
  const url = query ? `/owners/residents?${query}` : '/owners/residents';
  const { data } = await api.get<Resident[]>(url);
  return data;
};

export const fetchUsers = async (): Promise<User[]> => {
  const { data } = await api.get<User[]>('/auth/users');
  return data;
};

export const fetchOwnerById = async (id: number): Promise<Owner> => {
  const { data } = await api.get<Owner>(`/owners/${id}`);
  return data;
};

export const fetchMyOwnerRecord = async (): Promise<Owner> => {
  const { data } = await api.get<Owner>('/owners/me');
  return data;
};

export const updateMyOwnerRecord = async (payload: OwnerSelfUpdatePayload): Promise<Owner> => {
  const { data } = await api.put<Owner>('/owners/me', payload);
  return data;
};

export const updateUserProfile = async (payload: UserProfileUpdatePayload): Promise<User> => {
  const { data } = await api.patch<User>('/auth/me', payload);
  return data;
};

export const changePassword = async (payload: PasswordChangePayload): Promise<void> => {
  await api.post('/auth/me/change-password', payload);
};

export const archiveOwner = async (ownerId: number, payload: OwnerArchivePayload): Promise<Owner> => {
  const { data } = await api.post<Owner>(`/owners/${ownerId}/archive`, payload);
  return data;
};

export const restoreOwner = async (
  ownerId: number,
  payload: OwnerRestorePayload,
): Promise<Owner> => {
  const { data } = await api.post<Owner>(`/owners/${ownerId}/restore`, payload);
  return data;
};

export const updateOwner = async (ownerId: number, payload: OwnerUpdatePayload): Promise<Owner> => {
  const { data } = await api.put<Owner>(`/owners/${ownerId}`, payload);
  return data;
};

export const linkUserToOwner = async (
  ownerId: number,
  payload: { user_id: number; link_type?: string | null },
): Promise<Owner> => {
  const { data } = await api.post<Owner>(`/owners/${ownerId}/link-user`, payload);
  return data;
};

export const unlinkUserFromOwner = async (ownerId: number, userId: number): Promise<Owner> => {
  const { data } = await api.delete<Owner>(`/owners/${ownerId}/link-user/${userId}`);
  return data;
};

export const submitOwnerUpdateProposal = async (
  ownerId: number,
  proposedChanges: Record<string, unknown>,
) => {
  await api.post(`/owners/${ownerId}/proposals`, {
    proposed_changes: proposedChanges,
  });
};

export interface AnnouncementPayload {
  subject: string;
  body: string;
  delivery_methods: string[];
}

export const createAnnouncement = async (payload: AnnouncementPayload): Promise<Announcement> => {
  const { data } = await api.post<Announcement>('/communications/announcements', payload);
  return data;
};

export const fetchAnnouncements = async (): Promise<Announcement[]> => {
  const { data } = await api.get<Announcement[]>('/communications/announcements');
  return data;
};

export interface CommunicationMessagePayload {
  message_type: 'ANNOUNCEMENT' | 'BROADCAST';
  subject: string;
  body: string;
  segment?: string;
  delivery_methods?: string[];
}

export const createCommunicationMessage = async (
  payload: CommunicationMessagePayload,
): Promise<CommunicationMessage> => {
  const { data } = await api.post<CommunicationMessage>('/communications/messages', payload);
  return data;
};

export const fetchCommunicationMessages = async (): Promise<CommunicationMessage[]> => {
  const { data } = await api.get<CommunicationMessage[]>('/communications/messages');
  return data;
};

export interface EmailBroadcastPayload {
  subject: string;
  body: string;
  segment: string;
}

export const fetchBroadcastSegments = async (): Promise<EmailBroadcastSegment[]> => {
  const { data } = await api.get<EmailBroadcastSegment[]>('/communications/broadcast-segments');
  return data;
};

export const fetchEmailBroadcasts = async (): Promise<EmailBroadcast[]> => {
  const { data } = await api.get<EmailBroadcast[]>('/communications/broadcasts');
  return data;
};

export const createEmailBroadcast = async (payload: EmailBroadcastPayload): Promise<EmailBroadcast> => {
  const { data } = await api.post<EmailBroadcast>('/communications/broadcasts', payload);
  return data;
};

export interface TemplatePayload {
  name: string;
  type: string;
  subject: string;
  body: string;
  is_archived?: boolean;
}

export const fetchTemplates = async (params?: {
  type?: string;
  include_archived?: boolean;
  query?: string;
}): Promise<Template[]> => {
  const query = new URLSearchParams();
  if (params?.type) query.append('template_type', params.type);
  if (params?.include_archived) query.append('include_archived', 'true');
  if (params?.query) query.append('query', params.query);
  const url = query.toString() ? `/templates/?${query.toString()}` : '/templates/';
  const { data } = await api.get<Template[]>(url);
  return data;
};

export const createTemplate = async (payload: TemplatePayload): Promise<Template> => {
  const { data } = await api.post<Template>('/templates/', payload);
  return data;
};

export const updateTemplate = async (templateId: number, payload: Partial<TemplatePayload>): Promise<Template> => {
  const { data } = await api.patch<Template>(`/templates/${templateId}`, payload);
  return data;
};

export const fetchTemplateMergeTags = async (): Promise<TemplateMergeTag[]> => {
  const { data } = await api.get<TemplateMergeTag[]>('/templates/merge-tags');
  return data;
};

export const fetchDashboardReminders = async (): Promise<Reminder[]> => {
  const { data } = await api.get<Reminder[]>('/dashboard/reminders');
  return data;
};

export interface RegisterUserPayload {
  email: string;
  full_name?: string | null;
  password: string;
  role_ids: number[];
}

export interface ElectionCreatePayload {
  title: string;
  description?: string | null;
  opens_at?: string | null;
  closes_at?: string | null;
  status?: string | null;
}

export interface ElectionUpdatePayload {
  title?: string | null;
  description?: string | null;
  opens_at?: string | null;
  closes_at?: string | null;
  status?: string | null;
}

export interface ElectionCandidatePayload {
  display_name: string;
  statement?: string | null;
  owner_id?: number | null;
}

export interface ElectionVotePayload {
  token: string;
  candidate_id?: number | null;
  write_in?: string | null;
}

export const fetchRoles = async (): Promise<RoleOption[]> => {
  const { data } = await api.get<(Role & { permissions?: unknown })[]>('/auth/roles');
  return data.map((role) => ({
    id: role.id,
    name: role.name,
    description: role.description ?? null,
  }));
};

export const registerUser = async (payload: RegisterUserPayload): Promise<User> => {
  const { data } = await api.post<User>('/auth/register', payload);
  return data;
};

export const startTwoFactorSetup = async (): Promise<TwoFactorSetupResponse> => {
  const { data } = await api.post<TwoFactorSetupResponse>('/auth/2fa/setup');
  return data;
};

export const enableTwoFactor = async (otp: string): Promise<void> => {
  await api.post('/auth/2fa/enable', { otp });
};

export const disableTwoFactor = async (otp: string): Promise<void> => {
  await api.post('/auth/2fa/disable', { otp });
};

export const updateUserRoles = async (userId: number, roleIds: number[]): Promise<User> => {
  const { data } = await api.patch<User>(`/auth/users/${userId}/roles`, { role_ids: roleIds });
  return data;
};

export const fetchFineSchedules = async (): Promise<FineSchedule[]> => {
  const { data } = await api.get<FineSchedule[]>('/violations/fine-schedules');
  return data;
};

export interface ViolationFilters {
  status?: string;
  owner_id?: number;
  mine?: boolean;
}

export const fetchViolations = async (filters: ViolationFilters = {}): Promise<Violation[]> => {
  const params = new URLSearchParams();
  if (filters.status) params.append('status', filters.status);
  if (filters.owner_id) params.append('owner_id', String(filters.owner_id));
  if (filters.mine) params.append('mine', 'true');
  const query = params.toString();
  const url = query ? `/violations/?${query}` : '/violations/';
  const { data } = await api.get<Violation[]>(url);
  return data;
};

export const fetchNotifications = async (
  options: {
    includeRead?: boolean;
    limit?: number;
    levels?: string[];
    categories?: string[];
  } = {},
): Promise<Notification[]> => {
  const params = new URLSearchParams();
  if (options.includeRead === false) {
    params.append('include_read', 'false');
  }
  if (options.limit) {
    params.append('limit', String(options.limit));
  }
  if (options.levels?.length) {
    options.levels.forEach((level) => {
      if (level) {
        params.append('levels', level);
      }
    });
  }
  if (options.categories?.length) {
    options.categories.forEach((category) => {
      if (category) {
        params.append('categories', category);
      }
    });
  }
  const query = params.toString();
  const url = query ? `/notifications/?${query}` : '/notifications/';
  const { data } = await api.get<Notification[]>(url);
  return data;
};

export const markNotificationRead = async (notificationId: number): Promise<Notification> => {
  const { data } = await api.post<Notification>(`/notifications/${notificationId}/read`);
  return data;
};

export const markAllNotificationsRead = async (): Promise<{ updated: number }> => {
  const { data } = await api.post<{ updated: number }>('/notifications/read-all');
  return data;
};

export const sendNotificationBroadcast = async (payload: {
  title: string;
  message: string;
  level?: string;
  category?: string;
  link_url?: string | null;
  user_ids?: number[];
  roles?: string[];
}): Promise<{ created: number }> => {
  const { data } = await api.post<{ created: number }>('/notifications/broadcast', payload);
  return data;
};

export const createViolation = async (payload: ViolationCreatePayload): Promise<Violation> => {
  const { data } = await api.post<Violation>('/violations/', payload);
  return data;
};

export const updateViolation = async (
  violationId: number,
  payload: {
    category?: string;
    description?: string;
    location?: string;
    due_date?: string | null;
    hearing_date?: string | null;
    fine_amount?: string | null;
    resolution_notes?: string | null;
  },
): Promise<Violation> => {
  const { data } = await api.put<Violation>(`/violations/${violationId}`, payload);
  return data;
};

export const transitionViolation = async (
  violationId: number,
  payload: {
    target_status: string;
    note?: string;
    hearing_date?: string | null;
    fine_amount?: string | null;
    template_id?: number | null;
  },
): Promise<Violation> => {
  const { data } = await api.post<Violation>(`/violations/${violationId}/transition`, payload);
  return data;
};

export const assessAdditionalViolationFine = async (
  violationId: number,
  payload: { amount: string; template_id?: number | null },
): Promise<Violation> => {
  const { data } = await api.post<Violation>(`/violations/${violationId}/fines`, payload);
  return data;
};

export const fetchViolationNotices = async (violationId: number): Promise<ViolationNotice[]> => {
  const { data } = await api.get<ViolationNotice[]>(`/violations/${violationId}/notices`);
  return data;
};

export const submitAppeal = async (violationId: number, reason: string): Promise<Appeal> => {
  const { data } = await api.post<Appeal>(`/violations/${violationId}/appeals`, { reason });
  return data;
};

export const fetchViolationMessages = async (violationId: number): Promise<ViolationMessage[]> => {
  const { data } = await api.get<ViolationMessage[]>(`/violations/${violationId}/messages`);
  return data;
};

export const postViolationMessage = async (violationId: number, body: string): Promise<ViolationMessage> => {
  const { data } = await api.post<ViolationMessage>(`/violations/${violationId}/messages`, { body });
  return data;
};

export const fetchARCRequests = async (status?: string): Promise<ARCRequest[]> => {
  const params = status ? `?status=${encodeURIComponent(status)}` : '';
  const { data } = await api.get<ARCRequest[]>(`/arc/requests${params}`);
  return data;
};

export const createARCRequest = async (payload: {
  title: string;
  project_type?: string;
  description?: string;
  owner_id?: number;
}): Promise<ARCRequest> => {
  const { data } = await api.post<ARCRequest>('/arc/requests', payload);
  return data;
};

export const updateARCRequest = async (
  requestId: number,
  payload: { title?: string; project_type?: string | null; description?: string | null },
): Promise<ARCRequest> => {
  const { data } = await api.put<ARCRequest>(`/arc/requests/${requestId}`, payload);
  return data;
};

export const transitionARCRequest = async (
  requestId: number,
  payload: { target_status: string },
): Promise<ARCRequest> => {
  const { data } = await api.post<ARCRequest>(`/arc/requests/${requestId}/status`, payload);
  return data;
};

export const reopenARCRequest = async (requestId: number): Promise<ARCRequest> => {
  const { data } = await api.post<ARCRequest>(`/arc/requests/${requestId}/reopen`);
  return data;
};

export const uploadARCAttachment = async (requestId: number, file: File): Promise<ARCAttachment> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post<ARCAttachment>(`/arc/requests/${requestId}/attachments`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const addARCCondition = async (
  requestId: number,
  payload: { text: string; condition_type?: 'COMMENT' | 'REQUIREMENT' },
): Promise<ARCCondition> => {
  const { data } = await api.post<ARCCondition>(`/arc/requests/${requestId}/conditions`, payload);
  return data;
};

export const resolveARCCondition = async (
  requestId: number,
  conditionId: number,
  status: 'OPEN' | 'RESOLVED',
): Promise<ARCCondition> => {
  const { data } = await api.post<ARCCondition>(`/arc/requests/${requestId}/conditions/${conditionId}/resolve`, {
    status,
  });
  return data;
};

export const createARCInspection = async (
  requestId: number,
  payload: { scheduled_date?: string | null; result?: string | null; notes?: string | null },
): Promise<ARCInspection> => {
  const { data } = await api.post<ARCInspection>(`/arc/requests/${requestId}/inspections`, payload);
  return data;
};

const downloadCsv = async (endpoint: string): Promise<Blob> => {
  const response = await api.get(endpoint, { responseType: 'blob' });
  return response.data as Blob;
};

export const downloadARAgingReport = async (): Promise<Blob> => downloadCsv('/reports/ar-aging');

export const downloadCashFlowReport = async (): Promise<Blob> => downloadCsv('/reports/cash-flow');

export const downloadViolationsSummaryReport = async (): Promise<Blob> =>
  downloadCsv('/reports/violations-summary');

export const downloadArcSlaReport = async (): Promise<Blob> => downloadCsv('/reports/arc-sla');

export const fetchElections = async (options: { includeArchived?: boolean } = {}): Promise<ElectionListItem[]> => {
  const params = new URLSearchParams();
  if (options.includeArchived) {
    params.append('include_archived', 'true');
  }
  const query = params.toString();
  const url = query ? `/elections/?${query}` : '/elections/';
  const { data } = await api.get<ElectionListItem[]>(url);
  return data;
};

export const createElection = async (payload: ElectionCreatePayload): Promise<ElectionDetail> => {
  const { data } = await api.post<ElectionDetail>('/elections/', payload);
  return data;
};

export const updateElection = async (electionId: number, payload: ElectionUpdatePayload): Promise<ElectionDetail> => {
  const { data } = await api.patch<ElectionDetail>(`/elections/${electionId}`, payload);
  return data;
};

export const addElectionCandidate = async (
  electionId: number,
  payload: ElectionCandidatePayload,
): Promise<ElectionCandidate> => {
  const { data } = await api.post<ElectionCandidate>(`/elections/${electionId}/candidates`, payload);
  return data;
};

export const deleteElectionCandidate = async (electionId: number, candidateId: number): Promise<void> => {
  await api.delete(`/elections/${electionId}/candidates/${candidateId}`);
};

export const generateElectionBallots = async (electionId: number): Promise<ElectionAdminBallot[]> => {
  const { data } = await api.post<ElectionAdminBallot[]>(`/elections/${electionId}/ballots/generate`);
  return data;
};

export const fetchElectionDetail = async (electionId: number): Promise<ElectionDetail> => {
  const { data } = await api.get<ElectionDetail>(`/elections/${electionId}`);
  return data;
};

export const fetchElectionStats = async (electionId: number): Promise<ElectionStats> => {
  const { data } = await api.get<ElectionStats>(`/elections/${electionId}/stats`);
  return data;
};

export const downloadElectionResultsCsv = async (electionId: number): Promise<Blob> => {
  const response = await api.get(`/elections/${electionId}/results.csv`, { responseType: 'blob' });
  return response.data as Blob;
};

export const fetchElectionBallots = async (electionId: number): Promise<ElectionAdminBallot[]> => {
  const { data } = await api.get<ElectionAdminBallot[]>(`/elections/${electionId}/ballots`);
  return data;
};

export const fetchPublicElection = async (
  electionId: number,
  token: string,
): Promise<ElectionPublicDetail> => {
  const { data } = await publicApi.get<ElectionPublicDetail>(`/elections/public/${electionId}`, {
    params: { token },
  });
  return data;
};

export const submitPublicVote = async (electionId: number, payload: ElectionVotePayload): Promise<void> => {
  await publicApi.post(`/elections/public/${electionId}/vote`, payload);
};

export const uploadBankStatement = async (
  file: File,
  statementDate?: string,
  note?: string,
): Promise<BankImportSummary> => {
  const formData = new FormData();
  formData.append('file', file);
  if (statementDate) formData.append('statement_date', statementDate);
  if (note) formData.append('note', note);
  const { data } = await api.post<BankImportSummary>('/banking/reconciliations/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
};

export const fetchReconciliations = async (): Promise<Reconciliation[]> => {
  const { data } = await api.get<Reconciliation[]>('/banking/reconciliations');
  return data;
};

export const fetchReconciliationById = async (id: number): Promise<Reconciliation> => {
  const { data } = await api.get<Reconciliation>(`/banking/reconciliations/${id}`);
  return data;
};

export const fetchBankTransactions = async (status?: string): Promise<BankTransaction[]> => {
  const params = status ? `?status=${encodeURIComponent(status)}` : '';
  const { data } = await api.get<BankTransaction[]>(`/banking/transactions${params}`);
  return data;
};

export const sendInvoiceReminder = async (invoiceId: number): Promise<Blob> => {
  const { data } = await api.post<Blob>(`/billing/invoices/${invoiceId}/send-reminder`, null, {
    responseType: 'blob',
  });
  return data;
};

export default api;
