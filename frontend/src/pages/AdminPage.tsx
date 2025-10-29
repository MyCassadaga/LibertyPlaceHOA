import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { fetchRoles, registerUser, RegisterUserPayload } from '../services/api';
import { RoleOption } from '../types';

const AdminPage: React.FC = () => {
  const { user } = useAuth();
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [loadingRoles, setLoadingRoles] = useState(true);
  const [form, setForm] = useState<RegisterUserPayload>({
    email: '',
    full_name: '',
    password: '',
    role_id: 0,
  });
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const loadRoles = async () => {
      try {
        setLoadingRoles(true);
        const data = await fetchRoles();
        setRoles(data);
        const defaultRole = data.find((role) => role.name !== 'SYSADMIN');
        if (defaultRole) {
          setForm((prev) => ({ ...prev, role_id: defaultRole.id }));
        }
      } catch (err) {
        setError('Unable to load roles.');
      } finally {
        setLoadingRoles(false);
      }
    };
    void loadRoles();
  }, []);

  const roleOptions = useMemo(() => roles.filter((role) => role.name !== 'SYSADMIN'), [roles]);
  const selectedRole = useMemo(
    () => roleOptions.find((role) => role.id === form.role_id),
    [roleOptions, form.role_id],
  );

  const handleChange = (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = event.target;
    setForm((prev) => ({
      ...prev,
      [name]: name === 'role_id' ? Number(value) : value,
    }));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setStatus(null);
    if (!form.email || !form.password || !form.role_id) {
      setError('Email, password, and role are required.');
      return;
    }
    setSubmitting(true);
    try {
      await registerUser({
        email: form.email,
        full_name: form.full_name?.trim() ? form.full_name.trim() : undefined,
        password: form.password,
        role_id: form.role_id,
      });
      setStatus('User created successfully.');
      setForm((prev) => ({
        ...prev,
        email: '',
        full_name: '',
        password: '',
      }));
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
              onChange={handleChange}
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
              onChange={handleChange}
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
              onChange={handleChange}
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
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="role_id">
              Role
            </label>
            <select
              id="role_id"
              name="role_id"
              value={form.role_id}
              onChange={handleChange}
              className="w-full rounded border border-slate-300 px-3 py-2"
              disabled={loadingRoles || roleOptions.length === 0}
              required
            >
              {loadingRoles && <option value="">Loading roles…</option>}
              {!loadingRoles &&
                roleOptions.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
            </select>
            {selectedRole?.description && (
              <p className="mt-1 text-xs text-slate-500">{selectedRole.description}</p>
            )}
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
    </div>
  );
};

export default AdminPage;
