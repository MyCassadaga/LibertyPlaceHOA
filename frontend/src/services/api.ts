import axios from 'axios';

import {
  Announcement,
  BillingPolicy,
  BillingPolicyUpdatePayload,
  BillingSummary,
  Contract,
  EmailBroadcast,
  EmailBroadcastSegment,
  Invoice,
  Owner,
  Reminder,
  Role,
  RoleOption,
  User,
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

export const fetchOwners = async (): Promise<Owner[]> => {
  const { data } = await api.get<Owner[]>('/owners/');
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
  role_id: number;
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

export const sendInvoiceReminder = async (invoiceId: number): Promise<Blob> => {
  const { data } = await api.post<Blob>(`/billing/invoices/${invoiceId}/send-reminder`, null, {
    responseType: 'blob',
  });
  return data;
};

export default api;
