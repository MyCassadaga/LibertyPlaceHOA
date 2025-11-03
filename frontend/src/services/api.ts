import axios from 'axios';

import {
  Announcement,
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
  EmailBroadcast,
  EmailBroadcastSegment,
  FineSchedule,
  Invoice,
  Owner,
  OwnerSelfUpdatePayload,
  OwnerArchivePayload,
  OwnerRestorePayload,
  OwnerUpdatePayload,
  Reminder,
  Reconciliation,
  Role,
  RoleOption,
  Resident,
  PasswordChangePayload,
  User,
  UserProfileUpdatePayload,
  Violation,
  ViolationCreatePayload,
  ViolationNotice,
} from '../types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000',
});

export const setAuthToken = (token: string | null) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
};

export interface LoginResponse {
  access_token: string;
  token_type: string;
  roles: string[];
  primary_role?: string | null;
}

export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  const { data } = await api.post<LoginResponse>('/auth/login', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
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
  },
): Promise<Violation> => {
  const { data } = await api.post<Violation>(`/violations/${violationId}/transition`, payload);
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
  payload: { target_status: string; reviewer_user_id?: number | null; notes?: string | null },
): Promise<ARCRequest> => {
  const { data } = await api.post<ARCRequest>(`/arc/requests/${requestId}/status`, payload);
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
