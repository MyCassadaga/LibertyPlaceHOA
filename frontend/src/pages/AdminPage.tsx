import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { RegisterUserPayload, API_BASE_URL } from '../services/api';
import { User } from '../types';
import { formatUserRoles } from '../utils/roles';
import {
  useRolesQuery,
  useUsersQuery,
  useRegisterUserMutation,
  useUpdateUserRolesMutation,
  useLoginBackgroundQuery,
  useUploadLoginBackgroundMutation,
} from '../features/admin/hooks';
import { useNotificationBroadcastMutation } from '../features/notifications/hooks';

const AdminPage: React.FC = () => {
  const { user } = useAuth();
  const rolesQuery = useRolesQuery();
  const roles = useMemo(() => rolesQuery.data ?? [], [rolesQuery.data]);
  const loadingRoles = rolesQuery.isLoading;
  const usersQuery = useUsersQuery();
  const users = useMemo(() => usersQuery.data ?? [], [usersQuery.data]);
  const loadingUsers = usersQuery.isLoading;
  const usersFetchError = usersQuery.isError ? 'Unable to load user accounts.' : null;
  const rolesFetchError = rolesQuery.isError ? 'Unable to load roles.' : null;
  const registerUserMutation = useRegisterUserMutation();
  const updateUserRolesMutation = useUpdateUserRolesMutation();
  const loginBackgroundQuery = useLoginBackgroundQuery();
  const uploadBackgroundMutation = useUploadLoginBackgroundMutation();
  const broadcastMutation = useNotificationBroadcastMutation();
  const loginBackgroundUrl = toAbsoluteBackgroundUrl(loginBackgroundQuery.data?.url);
  const backgroundUploading = uploadBackgroundMutation.isPending;
  const combinedFormError = error ?? rolesFetchError;
  const [roleEdits, setRoleEdits] = useState<Record<number, number[]>>({});
  const [savingUserId, setSavingUserId] = useState<number | null>(null);
  const [roleStatus, setRoleStatus] = useState<string | null>(null);
  const [roleError, setRoleError] = useState<string | null>(null);

  const [form, setForm] = useState<RegisterUserPayload>({
    email: '',
    full_name: '',
    password: '',
    role_ids: [],
  });
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [backgroundStatus, setBackgroundStatus] = useState<string | null>(null);
  const [backgroundError, setBackgroundError] = useState<string | null>(null);
  const [backgroundFile, setBackgroundFile] = useState<File | null>(null);
  const [broadcastForm, setBroadcastForm] = useState({
    title: '',
    message: '',
    level: 'INFO',
    link_url: '',
    role_names: [] as string[],
  });
  const [broadcastStatus, setBroadcastStatus] = useState<string | null>(null);
  const [broadcastError, setBroadcastError] = useState<string | null>(null);

  const toAbsoluteBackgroundUrl = useCallback((url?: string | null) => {
    if (!url) return null;
    const base = API_BASE_URL.replace(/\/$/, '');
    const path = url.startsWith('/') ? url : `/${url}`;
    return `${base}${path}`;
  }, []);

  const normalizeRoleIds = useCallback((ids: number[]): number[] => {
    return Array.from(new Set(ids)).sort((a, b) => a - b);
  }, []);

  const getRoleIdsForUser = useCallback(
    (account: User): number[] => {
      if (account.roles && account.roles.length > 0) {
        return normalizeRoleIds(account.roles.map((role) => role.id));
      }
      if (account.primary_role) {
        return normalizeRoleIds([account.primary_role.id]);
      }
      if (account.role) {
        return normalizeRoleIds([account.role.id]);
      }
      return [];
    },
    [normalizeRoleIds],
  );

  const roleSetsEqual = useCallback(
    (left: number[], right: number[]) => {
      const normalizedLeft = normalizeRoleIds(left);
      const normalizedRight = normalizeRoleIds(right);
      if (normalizedLeft.length !== normalizedRight.length) {
        return false;
      }
      return normalizedLeft.every((value, index) => value === normalizedRight[index]);
    },
    [normalizeRoleIds],
  );

  const defaultRoleId = useMemo(() => {
    if (roles.length === 0) {
      return 0;
    }
    const homeowner = roles.find((role) => role.name === 'HOMEOWNER');
    return homeowner ? homeowner.id : roles[0].id;
  }, [roles]);

  useEffect(() => {
    if (!loadingRoles && roles.length > 0 && form.role_ids.length === 0 && defaultRoleId) {
      setForm((prev) => ({ ...prev, role_ids: [defaultRoleId] }));
    }
  }, [loadingRoles, roles, defaultRoleId, form.role_ids.length]);

  useEffect(() => {
    if (!users.length) {
      setRoleEdits({});
      return;
    }
    const mapped: Record<number, number[]> = {};
    users.forEach((account) => {
      mapped[account.id] = getRoleIdsForUser(account);
    });
    setRoleEdits(mapped);
  }, [users, getRoleIdsForUser]);

  const handleTextChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const toggleCreateRole = (roleId: number) => {
    setForm((prev) => {
      const current = new Set(prev.role_ids);
      if (current.has(roleId)) {
        current.delete(roleId);
      } else {
        current.add(roleId);
      }
      return {
        ...prev,
        role_ids: Array.from(current).sort((a, b) => a - b),
      };
    });
  };

  const handleToggleUserRole = (userId: number, roleId: number) => {
    setRoleEdits((prev) => {
      const account = users.find((entry) => entry.id === userId);
      const baseline = prev[userId] ?? (account ? getRoleIdsForUser(account) : []);
      const current = new Set(baseline);
      if (current.has(roleId)) {
        current.delete(roleId);
      } else {
        current.add(roleId);
      }
      return {
        ...prev,
        [userId]: Array.from(current).sort((a, b) => a - b),
      };
    });
  };

  const handleSaveRoles = async (userId: number) => {
    const selections = roleEdits[userId] ?? [];
    if (selections.length === 0) {
      setRoleError('Select at least one role before saving.');
      return;
    }
    setRoleStatus(null);
    setRoleError(null);
    setSavingUserId(userId);
    try {
      const updated = await updateUserRolesMutation.mutateAsync({ userId, roleIds: selections });
      setRoleEdits((prev) => ({
        ...prev,
        [userId]: getRoleIdsForUser(updated),
      }));
      setRoleStatus(`Updated roles for ${updated.email}.`);
    } catch (err) {
      console.error('Unable to update roles for user', err);
      setRoleError('Unable to update roles. Ensure the account retains at least one role and a SYSADMIN remains active.');
    } finally {
      setSavingUserId(null);
    }
  };

  const handleBackgroundFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setBackgroundStatus(null);
    setBackgroundError(null);
    const file = event.target.files?.[0] ?? null;
    setBackgroundFile(file);
  };

  const handleBackgroundUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (!backgroundFile) {
      setBackgroundError('Select an image before uploading.');
      return;
    }
    setBackgroundStatus(null);
    setBackgroundError(null);
    try {
      await uploadBackgroundMutation.mutateAsync(backgroundFile);
      setBackgroundStatus('Login background updated successfully.');
      setBackgroundFile(null);
      formElement.reset();
    } catch (err) {
      console.error('Unable to upload background image.', err);
      const message = err instanceof Error ? err.message : 'Unable to upload background image.';
      setBackgroundError(message);
    }
  };

  const handleBroadcastSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBroadcastStatus(null);
    setBroadcastError(null);
    if (!broadcastForm.title.trim() || !broadcastForm.message.trim()) {
      setBroadcastError('Title and message are required.');
      return;
    }
    if (broadcastForm.role_names.length === 0) {
      setBroadcastError('Select at least one recipient role.');
      return;
    }
    try {
      await broadcastMutation.mutateAsync({
        title: broadcastForm.title.trim(),
        message: broadcastForm.message.trim(),
        level: broadcastForm.level,
        link_url: broadcastForm.link_url.trim() || undefined,
        roles: broadcastForm.role_names,
      });
      setBroadcastStatus('Notification broadcast queued.');
      setBroadcastForm({ title: '', message: '', level: 'INFO', link_url: '', role_names: [] });
    } catch (err) {
      console.error('Unable to send notification broadcast.', err);
      setBroadcastError('Unable to send notification broadcast.');
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setStatus(null);
    if (!form.email || !form.password) {
      setError('Email and password are required.');
      return;
    }
    if (!form.role_ids || form.role_ids.length === 0) {
      setError('Select at least one role for the new account.');
      return;
    }
    setSubmitting(true);
    try {
      await registerUserMutation.mutateAsync({
        email: form.email,
        full_name: form.full_name?.trim() ? form.full_name.trim() : undefined,
        password: form.password,
        role_ids: form.role_ids,
      });
      setStatus('User created successfully.');
      setForm({
        email: '',
        full_name: '',
        password: '',
        role_ids: defaultRoleId ? [defaultRoleId] : [],
      });
    } catch (err) {
      console.error('Unable to create user account.', err);
      setError('Unable to create user. Ensure the email is unique and you are authorized.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">System Administration</h2>
        <p className="text-sm text-slate-500">
          Create new board, treasurer, secretary, auditor, or homeowner accounts.
        </p>
      </header>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-3 text-lg font-semibold text-slate-700">Create User</h3>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleTextChange}
              className="w-full rounded border border-slate-300 px-3 py-2"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="full_name">
              Full Name
            </label>
            <input
              id="full_name"
              name="full_name"
              value={form.full_name ?? ''}
              onChange={handleTextChange}
              className="w-full rounded border border-slate-300 px-3 py-2"
              placeholder="Optional"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="password">
              Temporary Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleTextChange}
              className="w-full rounded border border-slate-300 px-3 py-2"
              required
              minLength={8}
            />
            <p className="mt-1 text-xs text-slate-500">
              Share this password securely; users should change it after first login when password reset
              becomes available.
            </p>
          </div>
          <div>
            <span className="mb-1 block text-sm font-medium text-slate-600">Roles</span>
            {loadingRoles ? (
              <p className="text-xs text-slate-500">Loading roles…</p>
            ) : (
              <div className="flex flex-wrap gap-3">
                {roles.map((role) => {
                  const checked = form.role_ids.includes(role.id);
                  return (
                    <label key={role.id} className="inline-flex items-center gap-2 text-sm text-slate-600">
                      <input
                        type="checkbox"
                        className="rounded border-slate-300"
                        checked={checked}
                        onChange={() => toggleCreateRole(role.id)}
                      />
                      {role.name}
                    </label>
                  );
                })}
              </div>
            )}
            <p className="mt-1 text-xs text-slate-500">
              Assign at least one role. Include HOMEOWNER to automatically create a property profile for this account.
            </p>
          </div>

      {status && <p className="text-sm text-green-600">{status}</p>}
      {combinedFormError && <p className="text-sm text-red-600">{combinedFormError}</p>}

      <button
        type="submit"
        className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:opacity-60"
        disabled={submitting}
      >
        {submitting ? 'Creating…' : 'Create User'}
      </button>
    </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-2 text-lg font-semibold text-slate-700">Login Background</h3>
        <p className="mb-4 text-sm text-slate-500">
          Upload a PNG or JPG that appears behind the login form. Existing backgrounds are replaced immediately.
        </p>
        {loginBackgroundUrl ? (
          <div className="mb-4">
            <p className="mb-2 text-xs uppercase text-slate-500">Current preview</p>
            <div className="overflow-hidden rounded border border-slate-200">
              <img src={loginBackgroundUrl} alt="Login background" className="h-40 w-full object-cover" />
            </div>
          </div>
        ) : (
          <p className="mb-4 text-sm text-slate-500">No background configured. The login page uses a neutral gradient.</p>
        )}

        <form onSubmit={handleBackgroundUpload} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="admin-login-background">
              Upload new background
            </label>
            <input
              id="admin-login-background"
              type="file"
              accept="image/png, image/jpeg"
              onChange={handleBackgroundFileChange}
              className="block w-full text-sm text-slate-600 file:mr-4 file:rounded file:border-0 file:bg-primary-50 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-primary-600 hover:file:bg-primary-100"
            />
            <p className="mt-1 text-xs text-slate-500">Recommended size ≥ 1600px width. Maximum suggested upload 5MB.</p>
          </div>

          {backgroundError && <p className="text-sm text-red-600">{backgroundError}</p>}
          {backgroundStatus && <p className="text-sm text-green-600">{backgroundStatus}</p>}

          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
            disabled={backgroundUploading}
          >
            {backgroundUploading ? 'Uploading…' : 'Upload Background'}
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="mb-2 text-lg font-semibold text-slate-700">Manage Existing Accounts</h3>
        <p className="mb-4 text-sm text-slate-500">
          Adjust role assignments for existing users. Accounts can hold multiple roles, including HOMEOWNER.
        </p>
        {roleStatus && <p className="text-sm text-green-600">{roleStatus}</p>}
        {roleError && <p className="text-sm text-red-600">{roleError}</p>}
        {usersFetchError && <p className="text-sm text-red-600">{usersFetchError}</p>}
        {loadingUsers ? (
          <p className="text-sm text-slate-500">Loading user directory…</p>
        ) : users.length === 0 ? (
          <p className="text-sm text-slate-500">No user accounts found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Email</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Name</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Current Roles</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Assign Roles</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((account) => {
                  const baseline = getRoleIdsForUser(account);
                  const selected = roleEdits[account.id] ?? baseline;
                  const hasChanges = !roleSetsEqual(selected, baseline);
                  const disableSave = selected.length === 0 || !hasChanges || savingUserId === account.id;
                  return (
                    <tr key={account.id} className={!account.is_active ? 'bg-slate-100' : undefined}>
                      <td className="px-3 py-2">{account.email}</td>
                      <td className="px-3 py-2">{account.full_name ?? '—'}</td>
                      <td className="px-3 py-2">{formatUserRoles(account)}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-3">
                          {roles.map((role) => {
                            const checked = selected.includes(role.id);
                            return (
                              <label
                                key={`${account.id}-${role.id}`}
                                className="inline-flex items-center gap-2 text-xs text-slate-600"
                              >
                                <input
                                  type="checkbox"
                                  className="rounded border-slate-300"
                                  checked={checked}
                                  disabled={savingUserId === account.id}
                                  onChange={() => handleToggleUserRole(account.id, role.id)}
                                />
                                {role.name}
                              </label>
                            );
                          })}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => handleSaveRoles(account.id)}
                          className="rounded border border-primary-600 px-3 py-1 text-primary-600 hover:bg-primary-50 disabled:cursor-not-allowed disabled:border-slate-300 disabled:text-slate-400"
                          disabled={disableSave}
                        >
                          {savingUserId === account.id ? 'Saving…' : 'Save'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Broadcast Notification</h3>
        <p className="mb-4 text-sm text-slate-500">
          Send a manual alert to selected roles. Recipients will receive an in-app notification (and WebSocket ping if
          connected).
        </p>
        <form className="space-y-3" onSubmit={handleBroadcastSubmit}>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Title</span>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={broadcastForm.title}
              onChange={(event) => setBroadcastForm((prev) => ({ ...prev, title: event.target.value }))}
              required
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-slate-600">Message</span>
            <textarea
              className="w-full rounded border border-slate-300 px-3 py-2"
              rows={3}
              value={broadcastForm.message}
              onChange={(event) => setBroadcastForm((prev) => ({ ...prev, message: event.target.value }))}
              required
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Level</span>
              <select
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={broadcastForm.level}
                onChange={(event) => setBroadcastForm((prev) => ({ ...prev, level: event.target.value }))}
              >
                <option value="INFO">Info</option>
                <option value="SUCCESS">Success</option>
                <option value="WARNING">Warning</option>
                <option value="DANGER">Danger</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Link URL (optional)</span>
              <input
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={broadcastForm.link_url}
                onChange={(event) => setBroadcastForm((prev) => ({ ...prev, link_url: event.target.value }))}
                placeholder="https://example.com/details"
              />
            </label>
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Recipient Roles</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {roles.map((role) => (
                <label key={role.id} className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={broadcastForm.role_names.includes(role.name)}
                    onChange={(event) =>
                      setBroadcastForm((prev) => {
                        const current = new Set(prev.role_names);
                        if (event.target.checked) {
                          current.add(role.name);
                        } else {
                          current.delete(role.name);
                        }
                        return { ...prev, role_names: Array.from(current) };
                      })
                    }
                  />
                  {role.name}
                </label>
              ))}
            </div>
          </div>
          {broadcastError && <p className="text-sm text-red-600">{broadcastError}</p>}
          {broadcastStatus && <p className="text-sm text-green-600">{broadcastStatus}</p>}
          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={broadcastMutation.isPending}
          >
            {broadcastMutation.isPending ? 'Sending…' : 'Send Notification'}
          </button>
        </form>
      </section>
    </div>
  );
};

export default AdminPage;
