import { api } from '../lib/api/client';

export type WorkflowStatus = {
  key: string;
  label: string;
  category?: string | null;
};

export type WorkflowStatusOverride = WorkflowStatus & {
  enabled?: boolean;
};

export type WorkflowTransition = {
  from: string;
  to: string;
  label?: string | null;
};

export type WorkflowTransitionOverride = WorkflowTransition & {
  enabled?: boolean;
};

export type WorkflowNotificationTrigger = {
  from?: string | null;
  to?: string | null;
  status?: string | null;
};

export type WorkflowNotificationRecipient = {
  type: 'role' | 'user' | 'email';
  value: string;
};

export type WorkflowNotification = {
  event: 'transition' | 'status_entered';
  trigger: WorkflowNotificationTrigger;
  channels: string[];
  recipients: WorkflowNotificationRecipient[];
  template_key?: string | null;
  enabled?: boolean;
};

export type WorkflowBaseDefinition = {
  statuses: WorkflowStatus[];
  transitions: WorkflowTransition[];
  notifications: WorkflowNotification[];
};

export type WorkflowOverrides = {
  statuses?: WorkflowStatusOverride[];
  transitions?: WorkflowTransitionOverride[];
  notifications?: WorkflowNotification[];
};

export type WorkflowAdminView = {
  workflow_key: string;
  page_key?: string | null;
  title: string;
  base: WorkflowBaseDefinition;
  overrides?: WorkflowOverrides | null;
  effective: {
    statuses: WorkflowStatus[];
    transitions: WorkflowTransition[];
    notifications: WorkflowNotification[];
  };
};

export const listAdminWorkflows = async (): Promise<{ workflows: WorkflowAdminView[] }> => {
  const { data } = await api.get<{ workflows: WorkflowAdminView[] }>('/api/admin/workflows');
  return data;
};

export const getAdminWorkflow = async (workflowKey: string): Promise<WorkflowAdminView> => {
  const { data } = await api.get<WorkflowAdminView>(`/api/admin/workflows/${workflowKey}`);
  return data;
};

export const updateAdminWorkflow = async (
  workflowKey: string,
  overrides: WorkflowOverrides,
): Promise<WorkflowAdminView> => {
  const { data } = await api.put<WorkflowAdminView>(`/api/admin/workflows/${workflowKey}`, {
    overrides,
  });
  return data;
};
