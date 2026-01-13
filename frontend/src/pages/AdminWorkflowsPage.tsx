import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import Badge from '../components/Badge';
import {
  listAdminWorkflows,
  updateAdminWorkflow,
  WorkflowAdminView,
  WorkflowNotification,
  WorkflowNotificationRecipient,
  WorkflowOverrides,
  WorkflowStatus,
  WorkflowTransition,
} from '../api/adminWorkflows';

const adminWorkflowsQueryKey = ['admin', 'workflows'];

type TabKey = 'statuses' | 'transitions' | 'notifications';

type StatusRow = WorkflowStatus & {
  enabled: boolean;
  origin: 'base' | 'override';
  hasOverride: boolean;
};

type TransitionRow = WorkflowTransition & {
  enabled: boolean;
  origin: 'base' | 'override';
  hasOverride: boolean;
};

type NotificationRow = WorkflowNotification & {
  enabled: boolean;
  origin: 'base' | 'override';
  overrideIndex?: number;
};

const normalizeOverrides = (overrides?: WorkflowOverrides | null): WorkflowOverrides => ({
  statuses: overrides?.statuses?.map((status) => ({ ...status, enabled: status.enabled ?? true })) ?? [],
  transitions: overrides?.transitions?.map((transition) => ({ ...transition, enabled: transition.enabled ?? true })) ?? [],
  notifications:
    overrides?.notifications?.map((notification) => ({
      ...notification,
      enabled: notification.enabled ?? true,
    })) ?? [],
});

const notificationKey = (notification: WorkflowNotification) => {
  const trigger = notification.trigger ?? {};
  return [
    notification.event,
    trigger.from ?? '',
    trigger.to ?? '',
    trigger.status ?? '',
    notification.template_key ?? '',
  ].join('::');
};

const findStatus = (statuses: WorkflowStatus[], key: string) => statuses.find((status) => status.key === key);

const findTransition = (transitions: WorkflowTransition[], from: string, to: string) =>
  transitions.find((transition) => transition.from === from && transition.to === to);

const ensureOverrides = (
  drafts: Record<string, WorkflowOverrides>,
  workflow: WorkflowAdminView,
): WorkflowOverrides => {
  return drafts[workflow.workflow_key] ?? normalizeOverrides(workflow.overrides);
};

const AdminWorkflowsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const workflowsQuery = useQuery({
    queryKey: adminWorkflowsQueryKey,
    queryFn: listAdminWorkflows,
  });

  const [search, setSearch] = useState('');
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('statuses');
  const [drafts, setDrafts] = useState<Record<string, WorkflowOverrides>>({});
  const [dirtyMap, setDirtyMap] = useState<Record<string, boolean>>({});
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusForm, setStatusForm] = useState({ key: '', label: '', category: '' });
  const [transitionForm, setTransitionForm] = useState({ from: '', to: '', label: '' });
  const [notificationForm, setNotificationForm] = useState({
    event: 'transition',
    triggerFrom: '',
    triggerTo: '',
    triggerStatus: '',
    channels: '',
    recipients: '',
    templateKey: '',
  });
  const [formErrors, setFormErrors] = useState({
    statuses: null as string | null,
    transitions: null as string | null,
    notifications: null as string | null,
  });

  const workflows = useMemo(() => workflowsQuery.data?.workflows ?? [], [workflowsQuery.data]);

  const filteredWorkflows = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) return workflows;
    return workflows.filter((workflow) =>
      [workflow.page_key, workflow.title, workflow.workflow_key]
        .filter(Boolean)
        .some((value) => (value ?? '').toLowerCase().includes(needle)),
    );
  }, [search, workflows]);

  const selectedWorkflow = useMemo(
    () => workflows.find((workflow) => workflow.workflow_key === selectedKey) ?? null,
    [selectedKey, workflows],
  );

  const handleSelectWorkflow = (workflow: WorkflowAdminView) => {
    setSelectedKey(workflow.workflow_key);
    setDrafts((prev) => {
      if (prev[workflow.workflow_key]) {
        return prev;
      }
      return {
        ...prev,
        [workflow.workflow_key]: normalizeOverrides(workflow.overrides),
      };
    });
    setActiveTab('statuses');
    setStatusMessage(null);
    setErrorMessage(null);
    setFormErrors({ statuses: null, transitions: null, notifications: null });
  };

  const updateMutation = useMutation({
    mutationFn: ({ workflowKey, overrides }: { workflowKey: string; overrides: WorkflowOverrides }) =>
      updateAdminWorkflow(workflowKey, overrides),
    onSuccess: (updated) => {
      queryClient.setQueryData<{ workflows: WorkflowAdminView[] }>(adminWorkflowsQueryKey, (prev) => {
        if (!prev) return prev;
        return {
          workflows: prev.workflows.map((workflow) =>
            workflow.workflow_key === updated.workflow_key ? updated : workflow,
          ),
        };
      });
    },
  });

  const currentDraft = selectedWorkflow ? ensureOverrides(drafts, selectedWorkflow) : null;

  const statusRows = useMemo<StatusRow[]>(() => {
    if (!selectedWorkflow || !currentDraft) return [];
    const overrides = currentDraft.statuses ?? [];
    const overrideMap = new Map(overrides.map((status) => [status.key, status]));
    const baseKeys = new Set(selectedWorkflow.base.statuses.map((status) => status.key));
    const rows = selectedWorkflow.base.statuses.map((status) => {
      const override = overrideMap.get(status.key);
      const merged = { ...status, ...(override ?? {}) };
      return {
        key: status.key,
        label: merged.label,
        category: merged.category ?? null,
        enabled: override?.enabled ?? true,
        origin: 'base',
        hasOverride: Boolean(override),
      };
    });
    const overrideOnly = overrides
      .filter((status) => !baseKeys.has(status.key))
      .map((status) => ({
        key: status.key,
        label: status.label,
        category: status.category ?? null,
        enabled: status.enabled ?? true,
        origin: 'override' as const,
        hasOverride: true,
      }));
    return [...rows, ...overrideOnly];
  }, [currentDraft, selectedWorkflow]);

  const transitionRows = useMemo<TransitionRow[]>(() => {
    if (!selectedWorkflow || !currentDraft) return [];
    const overrides = currentDraft.transitions ?? [];
    const overrideMap = new Map(overrides.map((transition) => [`${transition.from}::${transition.to}`, transition]));
    const baseKeys = new Set(selectedWorkflow.base.transitions.map((transition) => `${transition.from}::${transition.to}`));
    const rows = selectedWorkflow.base.transitions.map((transition) => {
      const key = `${transition.from}::${transition.to}`;
      const override = overrideMap.get(key);
      const merged = { ...transition, ...(override ?? {}) };
      return {
        from: transition.from,
        to: transition.to,
        label: merged.label ?? '',
        enabled: override?.enabled ?? true,
        origin: 'base',
        hasOverride: Boolean(override),
      };
    });
    const overrideOnly = overrides
      .filter((transition) => !baseKeys.has(`${transition.from}::${transition.to}`))
      .map((transition) => ({
        from: transition.from,
        to: transition.to,
        label: transition.label ?? '',
        enabled: transition.enabled ?? true,
        origin: 'override' as const,
        hasOverride: true,
      }));
    return [...rows, ...overrideOnly];
  }, [currentDraft, selectedWorkflow]);

  const notificationRows = useMemo<NotificationRow[]>(() => {
    if (!selectedWorkflow || !currentDraft) return [];
    const overrides = currentDraft.notifications ?? [];
    const overrideMap = new Map(
      overrides.map((notification, index) => [notificationKey(notification), { notification, index }]),
    );
    const baseKeys = new Set(selectedWorkflow.base.notifications.map(notificationKey));
    const rows = selectedWorkflow.base.notifications.map((notification) => {
      const key = notificationKey(notification);
      const override = overrideMap.get(key);
      const merged = { ...notification, ...(override?.notification ?? {}) };
      return {
        ...merged,
        enabled: override?.notification.enabled ?? true,
        origin: 'base' as const,
        overrideIndex: override?.index,
      };
    });
    const overrideOnly = overrides
      .map((notification, index) => {
        if (baseKeys.has(notificationKey(notification))) {
          return null;
        }
        return {
          ...notification,
          enabled: notification.enabled ?? true,
          origin: 'override' as const,
          overrideIndex: index,
        };
      })
      .filter((row): row is NotificationRow => row !== null);
    return [...rows, ...overrideOnly];
  }, [currentDraft, selectedWorkflow]);

  const markDirty = (workflowKey: string) => {
    setDirtyMap((prev) => ({ ...prev, [workflowKey]: true }));
    setStatusMessage(null);
    setErrorMessage(null);
  };

  const updateStatuses = (workflow: WorkflowAdminView, statuses: WorkflowOverrides['statuses']) => {
    setDrafts((prev) => ({
      ...prev,
      [workflow.workflow_key]: { ...ensureOverrides(prev, workflow), statuses },
    }));
    markDirty(workflow.workflow_key);
  };

  const updateTransitions = (workflow: WorkflowAdminView, transitions: WorkflowOverrides['transitions']) => {
    setDrafts((prev) => ({
      ...prev,
      [workflow.workflow_key]: { ...ensureOverrides(prev, workflow), transitions },
    }));
    markDirty(workflow.workflow_key);
  };

  const updateNotifications = (workflow: WorkflowAdminView, notifications: WorkflowOverrides['notifications']) => {
    setDrafts((prev) => ({
      ...prev,
      [workflow.workflow_key]: { ...ensureOverrides(prev, workflow), notifications },
    }));
    markDirty(workflow.workflow_key);
  };

  const handleStatusToggle = (row: StatusRow, enabled: boolean) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.statuses ?? [])];
    const idx = overrides.findIndex((status) => status.key === row.key);
    const base = findStatus(selectedWorkflow.base.statuses, row.key) ?? row;
    if (idx >= 0) {
      overrides[idx] = { ...overrides[idx], enabled };
    } else {
      overrides.push({ key: base.key, label: base.label, category: base.category ?? null, enabled });
    }
    updateStatuses(selectedWorkflow, overrides);
  };

  const handleStatusLabelChange = (row: StatusRow, value: string) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.statuses ?? [])];
    const idx = overrides.findIndex((status) => status.key === row.key);
    const base = findStatus(selectedWorkflow.base.statuses, row.key) ?? row;
    if (idx >= 0) {
      overrides[idx] = { ...overrides[idx], label: value };
    } else {
      overrides.push({ key: base.key, label: value, category: base.category ?? null, enabled: true });
    }
    updateStatuses(selectedWorkflow, overrides);
  };

  const handleStatusCategoryChange = (row: StatusRow, value: string) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.statuses ?? [])];
    const idx = overrides.findIndex((status) => status.key === row.key);
    const base = findStatus(selectedWorkflow.base.statuses, row.key) ?? row;
    if (idx >= 0) {
      overrides[idx] = { ...overrides[idx], category: value || null };
    } else {
      overrides.push({ key: base.key, label: base.label, category: value || null, enabled: true });
    }
    updateStatuses(selectedWorkflow, overrides);
  };

  const handleTransitionToggle = (row: TransitionRow, enabled: boolean) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.transitions ?? [])];
    const idx = overrides.findIndex((transition) => transition.from === row.from && transition.to === row.to);
    const base = findTransition(selectedWorkflow.base.transitions, row.from, row.to) ?? row;
    if (idx >= 0) {
      overrides[idx] = { ...overrides[idx], enabled };
    } else {
      overrides.push({ from: base.from, to: base.to, label: base.label ?? '', enabled });
    }
    updateTransitions(selectedWorkflow, overrides);
  };

  const handleTransitionLabelChange = (row: TransitionRow, value: string) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.transitions ?? [])];
    const idx = overrides.findIndex((transition) => transition.from === row.from && transition.to === row.to);
    const base = findTransition(selectedWorkflow.base.transitions, row.from, row.to) ?? row;
    if (idx >= 0) {
      overrides[idx] = { ...overrides[idx], label: value };
    } else {
      overrides.push({ from: base.from, to: base.to, label: value, enabled: true });
    }
    updateTransitions(selectedWorkflow, overrides);
  };

  const handleNotificationToggle = (row: NotificationRow, enabled: boolean) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.notifications ?? [])];
    if (row.overrideIndex !== undefined) {
      overrides[row.overrideIndex] = { ...overrides[row.overrideIndex], enabled };
    } else {
      overrides.push({
        event: row.event,
        trigger: row.trigger,
        channels: row.channels,
        recipients: row.recipients,
        template_key: row.template_key ?? null,
        enabled,
      });
    }
    updateNotifications(selectedWorkflow, overrides);
  };

  const handleNotificationChange = (index: number, value: Partial<WorkflowNotification>) => {
    if (!selectedWorkflow) return;
    const overrides = [...(currentDraft?.notifications ?? [])];
    const current = overrides[index];
    if (!current) return;
    overrides[index] = { ...current, ...value };
    updateNotifications(selectedWorkflow, overrides);
  };

  const handleSave = async () => {
    if (!selectedWorkflow || !currentDraft) return;
    setErrorMessage(null);
    setStatusMessage(null);

    const statusKeys = new Set<string>();
    const transitions = new Set<string>();
    for (const status of currentDraft.statuses ?? []) {
      if (!status.key?.trim() || !status.label?.trim()) {
        setErrorMessage('Statuses require a key and label before saving.');
        return;
      }
      const key = status.key.trim();
      if (statusKeys.has(key)) {
        setErrorMessage('Status keys must be unique.');
        return;
      }
      statusKeys.add(key);
    }
    for (const transition of currentDraft.transitions ?? []) {
      if (!transition.from?.trim() || !transition.to?.trim()) {
        setErrorMessage('Transitions require both a from and to status before saving.');
        return;
      }
      const key = `${transition.from.trim()}::${transition.to.trim()}`;
      if (transitions.has(key)) {
        setErrorMessage('Transitions must be unique per from/to pair.');
        return;
      }
      transitions.add(key);
    }

    try {
      const updated = await updateMutation.mutateAsync({
        workflowKey: selectedWorkflow.workflow_key,
        overrides: currentDraft,
      });
      setDrafts((prev) => ({
        ...prev,
        [selectedWorkflow.workflow_key]: normalizeOverrides(updated.overrides),
      }));
      setDirtyMap((prev) => ({ ...prev, [selectedWorkflow.workflow_key]: false }));
      setStatusMessage('Workflow overrides saved successfully.');
    } catch (error) {
      console.error('Unable to update workflow overrides', error);
      setErrorMessage('Unable to save workflow overrides. Please try again.');
    }
  };

  const handleAddStatus = () => {
    if (!selectedWorkflow) return;
    const key = statusForm.key.trim();
    const label = statusForm.label.trim();
    if (!key || !label) {
      setFormErrors((prev) => ({ ...prev, statuses: 'Status key and label are required.' }));
      return;
    }
    const existingKeys = new Set([
      ...selectedWorkflow.base.statuses.map((status) => status.key),
      ...(currentDraft?.statuses ?? []).map((status) => status.key),
    ]);
    if (existingKeys.has(key)) {
      setFormErrors((prev) => ({ ...prev, statuses: 'Status key already exists.' }));
      return;
    }
    const overrides = [...(currentDraft?.statuses ?? [])];
    overrides.push({ key, label, category: statusForm.category.trim() || null, enabled: true });
    updateStatuses(selectedWorkflow, overrides);
    setStatusForm({ key: '', label: '', category: '' });
    setFormErrors((prev) => ({ ...prev, statuses: null }));
  };

  const handleAddTransition = () => {
    if (!selectedWorkflow) return;
    const from = transitionForm.from.trim();
    const to = transitionForm.to.trim();
    if (!from || !to) {
      setFormErrors((prev) => ({ ...prev, transitions: 'Transition requires both from and to values.' }));
      return;
    }
    const key = `${from}::${to}`;
    const existingTransitions = new Set([
      ...selectedWorkflow.base.transitions.map((transition) => `${transition.from}::${transition.to}`),
      ...(currentDraft?.transitions ?? []).map((transition) => `${transition.from}::${transition.to}`),
    ]);
    if (existingTransitions.has(key)) {
      setFormErrors((prev) => ({ ...prev, transitions: 'That transition already exists.' }));
      return;
    }
    const overrides = [...(currentDraft?.transitions ?? [])];
    overrides.push({ from, to, label: transitionForm.label.trim() || undefined, enabled: true });
    updateTransitions(selectedWorkflow, overrides);
    setTransitionForm({ from: '', to: '', label: '' });
    setFormErrors((prev) => ({ ...prev, transitions: null }));
  };

  const parseRecipients = (value: string): WorkflowNotificationRecipient[] => {
    const entries = value
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean);
    const recipients: WorkflowNotificationRecipient[] = [];
    for (const entry of entries) {
      const [type, ...rest] = entry.split(':');
      const trimmedType = type?.trim();
      const trimmedValue = rest.join(':').trim();
      if (!trimmedType || !trimmedValue) {
        throw new Error('Recipients must be formatted as type:value.');
      }
      if (!['role', 'user', 'email'].includes(trimmedType)) {
        throw new Error('Recipient type must be role, user, or email.');
      }
      recipients.push({ type: trimmedType as WorkflowNotificationRecipient['type'], value: trimmedValue });
    }
    return recipients;
  };

  const handleAddNotification = () => {
    if (!selectedWorkflow) return;
    const channels = notificationForm.channels
      .split(',')
      .map((channel) => channel.trim())
      .filter(Boolean);
    if (!channels.length) {
      setFormErrors((prev) => ({ ...prev, notifications: 'Notification channels are required.' }));
      return;
    }
    let recipients: WorkflowNotificationRecipient[] = [];
    try {
      recipients = parseRecipients(notificationForm.recipients);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Invalid recipients format.';
      setFormErrors((prev) => ({ ...prev, notifications: message }));
      return;
    }
    if (!recipients.length) {
      setFormErrors((prev) => ({ ...prev, notifications: 'At least one recipient is required.' }));
      return;
    }
    const overrides = [...(currentDraft?.notifications ?? [])];
    overrides.push({
      event: notificationForm.event as WorkflowNotification['event'],
      trigger: {
        from: notificationForm.triggerFrom.trim() || null,
        to: notificationForm.triggerTo.trim() || null,
        status: notificationForm.triggerStatus.trim() || null,
      },
      channels,
      recipients,
      template_key: notificationForm.templateKey.trim() || null,
      enabled: true,
    });
    updateNotifications(selectedWorkflow, overrides);
    setNotificationForm({
      event: 'transition',
      triggerFrom: '',
      triggerTo: '',
      triggerStatus: '',
      channels: '',
      recipients: '',
      templateKey: '',
    });
    setFormErrors((prev) => ({ ...prev, notifications: null }));
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold text-primary-600">Workflows</h2>
          <p className="text-sm text-slate-500">Manage workflow statuses, transitions, and notifications.</p>
        </div>
        <div className="w-full sm:w-64">
          <label className="sr-only" htmlFor="workflow-search">
            Search workflows
          </label>
          <input
            id="workflow-search"
            type="search"
            className="w-full rounded border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary-400 focus:outline-none focus:ring-1 focus:ring-primary-300"
            placeholder="Search workflows"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      <div className="overflow-hidden rounded border border-slate-200">
        <table className="w-full border-collapse text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2">Page</th>
              <th className="px-3 py-2">Workflow</th>
              <th className="px-3 py-2">Statuses</th>
              <th className="px-3 py-2">Transitions</th>
              <th className="px-3 py-2">Notifications</th>
              <th className="px-3 py-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {workflowsQuery.isLoading && (
              <tr>
                <td className="px-3 py-4 text-sm text-slate-500" colSpan={6}>
                  Loading workflows…
                </td>
              </tr>
            )}
            {!workflowsQuery.isLoading && filteredWorkflows.length === 0 && (
              <tr>
                <td className="px-3 py-4 text-sm text-slate-500" colSpan={6}>
                  No workflows match your search.
                </td>
              </tr>
            )}
            {filteredWorkflows.map((workflow) => (
              <tr
                key={workflow.workflow_key}
                className={selectedKey === workflow.workflow_key ? 'bg-primary-50/50' : undefined}
              >
                <td className="px-3 py-2 text-sm text-slate-700">{workflow.page_key ?? '—'}</td>
                <td className="px-3 py-2">
                  <div className="text-sm font-medium text-slate-700">{workflow.title}</div>
                  <div className="text-xs text-slate-500">{workflow.workflow_key}</div>
                </td>
                <td className="px-3 py-2 text-sm text-slate-600">{workflow.effective.statuses.length}</td>
                <td className="px-3 py-2 text-sm text-slate-600">{workflow.effective.transitions.length}</td>
                <td className="px-3 py-2 text-sm text-slate-600">{workflow.effective.notifications.length}</td>
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    className="rounded border border-primary-200 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-50"
                    onClick={() => handleSelectWorkflow(workflow)}
                  >
                    {selectedKey === workflow.workflow_key ? 'Editing' : 'Edit'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {selectedWorkflow && currentDraft && (
        <section className="space-y-4 rounded border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-700">{selectedWorkflow.title}</h3>
              <p className="text-xs text-slate-500">
                Workflow key: <span className="font-semibold">{selectedWorkflow.workflow_key}</span>
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded border border-primary-500 px-4 py-2 text-sm font-semibold text-primary-700 hover:bg-primary-50"
                onClick={handleSave}
                disabled={!dirtyMap[selectedWorkflow.workflow_key] || updateMutation.isPending}
              >
                {updateMutation.isPending ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
          {(statusMessage || errorMessage) && (
            <div className="space-y-1">
              {statusMessage && <p className="text-sm text-emerald-600">{statusMessage}</p>}
              {errorMessage && <p className="text-sm text-rose-600">{errorMessage}</p>}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {(['statuses', 'transitions', 'notifications'] as TabKey[]).map((tab) => (
              <button
                key={tab}
                type="button"
                className={`rounded px-3 py-1 text-sm font-semibold transition-colors ${
                  activeTab === tab ? 'bg-primary-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
                onClick={() => setActiveTab(tab)}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>

          {activeTab === 'statuses' && (
            <div className="space-y-4">
              <table className="w-full border-collapse text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Enabled</th>
                    <th className="px-2 py-2">Key</th>
                    <th className="px-2 py-2">Label</th>
                    <th className="px-2 py-2">Category</th>
                    <th className="px-2 py-2">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {statusRows.map((row) => (
                    <tr key={row.key}>
                      <td className="px-2 py-2">
                        <input
                          type="checkbox"
                          checked={row.enabled}
                          onChange={(event) => handleStatusToggle(row, event.target.checked)}
                        />
                      </td>
                      <td className="px-2 py-2 text-xs font-semibold text-slate-600">{row.key}</td>
                      <td className="px-2 py-2">
                        <input
                          type="text"
                          className="w-full rounded border border-slate-200 px-2 py-1 text-xs"
                          value={row.label}
                          onChange={(event) => handleStatusLabelChange(row, event.target.value)}
                        />
                      </td>
                      <td className="px-2 py-2">
                        <input
                          type="text"
                          className="w-full rounded border border-slate-200 px-2 py-1 text-xs"
                          value={row.category ?? ''}
                          onChange={(event) => handleStatusCategoryChange(row, event.target.value)}
                        />
                      </td>
                      <td className="px-2 py-2">
                        <Badge tone={row.origin === 'base' ? 'info' : 'neutral'}>
                          {row.origin === 'base' ? 'Base' : 'Override'}
                        </Badge>
                        {row.hasOverride && row.origin === 'base' && (
                          <Badge tone="warning" className="ml-2">
                            Overridden
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="rounded border border-slate-200 p-3">
                <h4 className="text-sm font-semibold text-slate-700">Add status override</h4>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Key"
                    value={statusForm.key}
                    onChange={(event) => setStatusForm((prev) => ({ ...prev, key: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Label"
                    value={statusForm.label}
                    onChange={(event) => setStatusForm((prev) => ({ ...prev, label: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Category"
                    value={statusForm.category}
                    onChange={(event) => setStatusForm((prev) => ({ ...prev, category: event.target.value }))}
                  />
                </div>
                {formErrors.statuses && <p className="mt-2 text-xs text-rose-600">{formErrors.statuses}</p>}
                <button
                  type="button"
                  className="mt-3 rounded border border-primary-200 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-50"
                  onClick={handleAddStatus}
                >
                  Add status
                </button>
              </div>
            </div>
          )}

          {activeTab === 'transitions' && (
            <div className="space-y-4">
              <table className="w-full border-collapse text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Enabled</th>
                    <th className="px-2 py-2">From</th>
                    <th className="px-2 py-2">To</th>
                    <th className="px-2 py-2">Label</th>
                    <th className="px-2 py-2">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {transitionRows.map((row) => (
                    <tr key={`${row.from}-${row.to}`}>
                      <td className="px-2 py-2">
                        <input
                          type="checkbox"
                          checked={row.enabled}
                          onChange={(event) => handleTransitionToggle(row, event.target.checked)}
                        />
                      </td>
                      <td className="px-2 py-2 text-xs font-semibold text-slate-600">{row.from}</td>
                      <td className="px-2 py-2 text-xs font-semibold text-slate-600">{row.to}</td>
                      <td className="px-2 py-2">
                        <input
                          type="text"
                          className="w-full rounded border border-slate-200 px-2 py-1 text-xs"
                          value={row.label ?? ''}
                          onChange={(event) => handleTransitionLabelChange(row, event.target.value)}
                        />
                      </td>
                      <td className="px-2 py-2">
                        <Badge tone={row.origin === 'base' ? 'info' : 'neutral'}>
                          {row.origin === 'base' ? 'Base' : 'Override'}
                        </Badge>
                        {row.hasOverride && row.origin === 'base' && (
                          <Badge tone="warning" className="ml-2">
                            Overridden
                          </Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="rounded border border-slate-200 p-3">
                <h4 className="text-sm font-semibold text-slate-700">Add transition override</h4>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="From status"
                    value={transitionForm.from}
                    onChange={(event) => setTransitionForm((prev) => ({ ...prev, from: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="To status"
                    value={transitionForm.to}
                    onChange={(event) => setTransitionForm((prev) => ({ ...prev, to: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Label"
                    value={transitionForm.label}
                    onChange={(event) => setTransitionForm((prev) => ({ ...prev, label: event.target.value }))}
                  />
                </div>
                {formErrors.transitions && <p className="mt-2 text-xs text-rose-600">{formErrors.transitions}</p>}
                <button
                  type="button"
                  className="mt-3 rounded border border-primary-200 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-50"
                  onClick={handleAddTransition}
                >
                  Add transition
                </button>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-4">
              <table className="w-full border-collapse text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-2 py-2">Enabled</th>
                    <th className="px-2 py-2">Event</th>
                    <th className="px-2 py-2">Trigger</th>
                    <th className="px-2 py-2">Channels</th>
                    <th className="px-2 py-2">Recipients</th>
                    <th className="px-2 py-2">Template</th>
                    <th className="px-2 py-2">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {notificationRows.map((row, index) => {
                    const triggerSummary = [
                      row.trigger?.from ? `from ${row.trigger.from}` : null,
                      row.trigger?.to ? `to ${row.trigger.to}` : null,
                      row.trigger?.status ? `status ${row.trigger.status}` : null,
                    ]
                      .filter(Boolean)
                      .join(', ');
                    const recipientsValue = row.recipients
                      .map((recipient) => `${recipient.type}:${recipient.value}`)
                      .join(', ');
                    const editable = row.origin === 'override' || row.overrideIndex !== undefined;
                    return (
                      <tr key={`${notificationKey(row)}-${index}`}>
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            checked={row.enabled}
                            onChange={(event) => handleNotificationToggle(row, event.target.checked)}
                          />
                        </td>
                        <td className="px-2 py-2 text-xs font-semibold text-slate-600">{row.event}</td>
                        <td className="px-2 py-2 text-xs text-slate-600">{triggerSummary || '—'}</td>
                        <td className="px-2 py-2">
                          <input
                            type="text"
                            disabled={!editable}
                            className="w-full rounded border border-slate-200 px-2 py-1 text-xs disabled:bg-slate-50"
                            value={row.channels.join(', ')}
                            onChange={(event) => {
                              if (row.overrideIndex === undefined) return;
                              handleNotificationChange(row.overrideIndex, {
                                channels: event.target.value
                                  .split(',')
                                  .map((value) => value.trim())
                                  .filter(Boolean),
                              });
                            }}
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            type="text"
                            disabled={!editable}
                            className="w-full rounded border border-slate-200 px-2 py-1 text-xs disabled:bg-slate-50"
                            value={recipientsValue}
                            onChange={(event) => {
                              if (row.overrideIndex === undefined) return;
                              let recipients: WorkflowNotificationRecipient[] = [];
                              try {
                                recipients = parseRecipients(event.target.value);
                              } catch (error) {
                                return;
                              }
                              handleNotificationChange(row.overrideIndex, { recipients });
                            }}
                          />
                        </td>
                        <td className="px-2 py-2">
                          <input
                            type="text"
                            disabled={!editable}
                            className="w-full rounded border border-slate-200 px-2 py-1 text-xs disabled:bg-slate-50"
                            value={row.template_key ?? ''}
                            onChange={(event) => {
                              if (row.overrideIndex === undefined) return;
                              handleNotificationChange(row.overrideIndex, {
                                template_key: event.target.value.trim() || null,
                              });
                            }}
                          />
                        </td>
                        <td className="px-2 py-2">
                          <Badge tone={row.origin === 'base' ? 'info' : 'neutral'}>
                            {row.origin === 'base' ? 'Base' : 'Override'}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="rounded border border-slate-200 p-3">
                <h4 className="text-sm font-semibold text-slate-700">Add notification override</h4>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <select
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    value={notificationForm.event}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, event: event.target.value }))}
                  >
                    <option value="transition">transition</option>
                    <option value="status_entered">status_entered</option>
                  </select>
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Template key"
                    value={notificationForm.templateKey}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, templateKey: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Trigger from"
                    value={notificationForm.triggerFrom}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, triggerFrom: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Trigger to"
                    value={notificationForm.triggerTo}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, triggerTo: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Trigger status"
                    value={notificationForm.triggerStatus}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, triggerStatus: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs"
                    placeholder="Channels (email, sms)"
                    value={notificationForm.channels}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, channels: event.target.value }))}
                  />
                  <input
                    type="text"
                    className="rounded border border-slate-200 px-2 py-1 text-xs sm:col-span-2"
                    placeholder="Recipients (role:SYSADMIN, email:ops@example.com)"
                    value={notificationForm.recipients}
                    onChange={(event) => setNotificationForm((prev) => ({ ...prev, recipients: event.target.value }))}
                  />
                </div>
                {formErrors.notifications && <p className="mt-2 text-xs text-rose-600">{formErrors.notifications}</p>}
                <button
                  type="button"
                  className="mt-3 rounded border border-primary-200 px-3 py-1 text-xs font-semibold text-primary-700 hover:bg-primary-50"
                  onClick={handleAddNotification}
                >
                  Add notification
                </button>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default AdminWorkflowsPage;
