import React, { useCallback, useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  fetchRoles,
  fetchUsers,
  registerUser,
  updateUserRoles,
  fetchLoginBackground,
  uploadLoginBackground,
  RegisterUserPayload,
} from '../services/api';
import { API_BASE_URL } from '../services/api';
import { RoleOption, User } from '../types';
import { formatUserRoles } from '../utils/roles';

const AdminPage: React.FC = () => {
  const { user } = useAuth();
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loadingRoles, setLoadingRoles] = useState(true);
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);
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
  const [loginBackgroundUrl, setLoginBackgroundUrl] = useState<string | null>(null);
  const [backgroundStatus, setBackgroundStatus] = useState<string | null>(null);
  const [backgroundError, setBackgroundError] = useState<string | null>(null);
  const [backgroundUploading, setBackgroundUploading] = useState(false);
  const [backgroundFile, setBackgroundFile] = useState<File | null>(null);

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

  useEffect(() => {
    const loadRoles = async () => {
      try {
        setLoadingRoles(true);
        const data = await fetchRoles();
        setRoles(data);
      } catch (err) {
        setError('Unable to load roles.');
      } finally {
        setLoadingRoles(false);
      }
    };
    void loadRoles();
  }, []);

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

  const loadUsers = useCallback(async () => {
    try {
      setLoadingUsers(true);
      setUsersError(null);
      const data = await fetchUsers();
      setUsers(data);
      const mapped: Record<number, number[]> = {};
      data.forEach((account) => {
        mapped[account.id] = getRoleIdsForUser(account);
      });
      setRoleEdits(mapped);
    } catch (err) {
      setUsersError('Unable to load user accounts.');
    } finally {
      setLoadingUsers(false);
    }
  }, [getRoleIdsForUser]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    const loadBackground = async () => {
      try {
        const data = await fetchLoginBackground();
        setLoginBackgroundUrl(toAbsoluteBackgroundUrl(data.url));
      } catch {
        setLoginBackgroundUrl(null);
      }
    };
    void loadBackground();
  }, [toAbsoluteBackgroundUrl]);

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
      const updated = await updateUserRoles(userId, selections);
      setUsers((prev) => prev.map((entry) => (entry.id === userId ? updated : entry)));
      setRoleEdits((prev) => ({
        ...prev,
        [userId]: getRoleIdsForUser(updated),
      }));
      setUsersError(null);
      setRoleStatus(`Updated roles for ${updated.email}.`);
    } catch (err) {
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
    setBackgroundUploading(true);
    setBackgroundStatus(null);
    setBackgroundError(null);
    try {
      const data = await uploadLoginBackground(backgroundFile);
      setLoginBackgroundUrl(toAbsoluteBackgroundUrl(data.url));
      setBackgroundStatus('Login background updated successfully.');
      setBackgroundFile(null);
      formElement.reset();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to upload background image.';
      setBackgroundError(message);
    } finally {
      setBackgroundUploading(false);
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
      await registerUser({
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
      await loadUsers();
    } catch (err) {
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
      {error && <p className="text-sm text-red-600">{error}</p>}

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
        {usersError && <p className="text-sm text-red-600">{usersError}</p>}
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
    </div>
  );
};

export default AdminPage;
