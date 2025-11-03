import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import {
  archiveOwner,
  fetchOwnerById,
  fetchResidents,
  linkUserToOwner,
  restoreOwner,
  unlinkUserFromOwner,
  updateOwner,
} from '../services/api';
import { Owner, OwnerUpdatePayload, Resident, User } from '../types';
import { formatUserRoles, userHasRole } from '../utils/roles';

const OwnersPage: React.FC = () => {
  const { user } = useAuth();
  const isSysAdmin = userHasRole(user, 'SYSADMIN');
  const [residents, setResidents] = useState<Resident[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [processingOwnerId, setProcessingOwnerId] = useState<number | null>(null);
  const [editingOwner, setEditingOwner] = useState<Owner | null>(null);
  const [ownerForm, setOwnerForm] = useState<(OwnerUpdatePayload & { notesText: string }) | null>(null);
  const [savingOwner, setSavingOwner] = useState(false);
  const [selectedLinkUserId, setSelectedLinkUserId] = useState<number | ''>('');
  const [linkingUserId, setLinkingUserId] = useState<number | null>(null);

  const buildOwnerForm = (owner: Owner): (OwnerUpdatePayload & { notesText: string }) => ({
    primary_name: owner.primary_name ?? '',
    secondary_name: owner.secondary_name ?? '',
    lot: owner.former_lot ?? owner.lot ?? '',
    property_address: owner.property_address ?? '',
    mailing_address: owner.mailing_address ?? '',
    primary_email: owner.primary_email ?? '',
    secondary_email: owner.secondary_email ?? '',
    primary_phone: owner.primary_phone ?? '',
    secondary_phone: owner.secondary_phone ?? '',
    occupancy_status: owner.occupancy_status ?? '',
    emergency_contact: owner.emergency_contact ?? '',
    is_rental: owner.is_rental ?? false,
    notes: undefined,
    notesText: owner.notes ?? '',
  });

  const loadResidents = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchResidents({ includeArchived: true });
      setResidents(data);
    } catch (err) {
      setError('Unable to load resident roster.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadResidents();
  }, []);

  const ownerRows = useMemo(() => residents.filter((record) => record.owner), [residents]);
  const activeOwnerRows = useMemo(
    () => ownerRows.filter((record) => !record.owner!.is_archived),
    [ownerRows],
  );
  const archivedOwnerRows = useMemo(
    () => ownerRows.filter((record) => record.owner!.is_archived),
    [ownerRows],
  );

  const accountRows = useMemo(() => residents.filter((record) => record.user), [residents]);
  const unlinkedAccounts = useMemo(
    () => accountRows.filter((record) => !record.owner),
    [accountRows],
  );
  const inactiveAccounts = useMemo(
    () => accountRows.filter((record) => record.user && !record.user.is_active),
    [accountRows],
  );

  const linkedAccounts = useMemo<User[]>(() => {
    if (!editingOwner) return [];
    return residents
      .filter((record) => record.owner?.id === editingOwner.id && record.user)
      .map((record) => record.user!);
  }, [residents, editingOwner]);

  const availableAccounts = useMemo<User[]>(() => {
    if (!editingOwner) return [];
    const linkedIds = new Set(linkedAccounts.map((account) => account.id));
    return accountRows
      .filter((record) => record.user)
      .filter((record) => !record.owner || record.owner.id === editingOwner.id)
      .map((record) => record.user!)
      .filter((user) => !linkedIds.has(user.id));
  }, [accountRows, editingOwner, linkedAccounts]);

  const openEdit = (owner: Owner) => {
    setStatus(null);
    setError(null);
    setOwnerForm(buildOwnerForm(owner));
    setEditingOwner(owner);
    setSelectedLinkUserId('');
    setLinkingUserId(null);
  };

  const closeEdit = () => {
    setEditingOwner(null);
    setOwnerForm(null);
    setSavingOwner(false);
    setSelectedLinkUserId('');
    setLinkingUserId(null);
  };

  const handleOwnerFieldChange = (field: keyof OwnerUpdatePayload | 'notesText', value: string | boolean) => {
    setOwnerForm((prev) => {
      if (!prev) return prev;
      const next = { ...prev };
      if (field === 'is_rental') {
        next.is_rental = Boolean(value);
      } else if (field === 'notesText') {
        next.notesText = String(value);
      } else {
        next[field] = typeof value === 'string' ? value : value ? 'true' : 'false';
      }
      return next;
    });
  };

  const handleOwnerSave = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingOwner || !ownerForm) return;

    const trim = (raw?: string | null) => {
      if (raw == null) return undefined;
      const value = raw.toString().trim();
      return value.length > 0 ? value : undefined;
    };

    const payload: OwnerUpdatePayload = {
      primary_name: trim(ownerForm.primary_name),
      secondary_name: trim(ownerForm.secondary_name),
      property_address: trim(ownerForm.property_address),
      mailing_address: trim(ownerForm.mailing_address),
      primary_email: trim(ownerForm.primary_email),
      secondary_email: trim(ownerForm.secondary_email),
      primary_phone: trim(ownerForm.primary_phone),
      secondary_phone: trim(ownerForm.secondary_phone),
      occupancy_status: trim(ownerForm.occupancy_status),
      emergency_contact: trim(ownerForm.emergency_contact),
      is_rental: typeof ownerForm.is_rental === 'boolean' ? ownerForm.is_rental : undefined,
      notes: trim(ownerForm.notesText),
    };

    if (!payload.primary_name || !payload.property_address) {
      setError('Primary name and property address are required.');
      return;
    }

    setSavingOwner(true);
    try {
      await updateOwner(editingOwner.id, payload);
      setStatus('Owner details updated.');
      await loadResidents();
      closeEdit();
    } catch (err) {
      setError('Unable to update owner. Please try again.');
    } finally {
      setSavingOwner(false);
    }
  };

  const handleLinkUser = async () => {
    if (!editingOwner || !selectedLinkUserId) return;
    setLinkingUserId(Number(selectedLinkUserId));
    setStatus(null);
    setError(null);
    try {
      await linkUserToOwner(editingOwner.id, { user_id: Number(selectedLinkUserId) });
      const refreshed = await fetchOwnerById(editingOwner.id);
      setEditingOwner(refreshed);
      setOwnerForm(buildOwnerForm(refreshed));
      await loadResidents();
      setStatus('Linked account to owner.');
      setSelectedLinkUserId('');
    } catch (err) {
      setError('Unable to link account to owner.');
    } finally {
      setLinkingUserId(null);
    }
  };

  const handleUnlinkUser = async (userId: number) => {
    if (!editingOwner) return;
    const confirm = window.confirm('Remove this linked account from the owner record?');
    if (!confirm) return;
    setLinkingUserId(userId);
    setStatus(null);
    setError(null);
    try {
      await unlinkUserFromOwner(editingOwner.id, userId);
      const refreshed = await fetchOwnerById(editingOwner.id);
      setEditingOwner(refreshed);
      setOwnerForm(buildOwnerForm(refreshed));
      await loadResidents();
      setStatus('Unlinked account from owner.');
    } catch (err) {
      setError('Unable to unlink account from owner.');
    } finally {
      setLinkingUserId(null);
    }
  };

  const formatProperty = (owner: Owner) => owner.property_address || 'Property address pending';
  const formatOwnerId = (owner: Owner) => `Owner #${owner.id.toString().padStart(3, '0')}`;
  const formatDate = (value?: string | null) =>
    value ? new Date(value).toLocaleString() : '—';

  const handleArchive = async (ownerId: number) => {
    if (!isSysAdmin) {
      return;
    }
    const confirmArchive = window.confirm(
      'Archiving will freeze billing and move this owner record into the archived roster. Continue?',
    );
    if (!confirmArchive) {
      return;
    }
    const reasonInput = window.prompt('Enter an archive reason (optional):') ?? '';
    const reason = reasonInput.trim() || undefined;
    setProcessingOwnerId(ownerId);
    setStatus(null);
    setError(null);
    try {
      await archiveOwner(ownerId, { reason });
      setStatus('Owner archived successfully.');
      await loadResidents();
    } catch (err) {
      setError('Unable to archive owner. Please try again.');
    } finally {
      setProcessingOwnerId(null);
    }
  };

  const handleRestore = async (ownerId: number) => {
    if (!isSysAdmin) {
      return;
    }
    const confirmRestore = window.confirm(
      'Restore this archived owner? You can optionally reactivate linked logins after restoring.',
    );
    if (!confirmRestore) {
      return;
    }
    const reactivateUser = window.confirm('Reactivate linked user accounts now? Click OK for yes.');
    setProcessingOwnerId(ownerId);
    setStatus(null);
    setError(null);
    try {
      await restoreOwner(ownerId, { reactivate_user: reactivateUser });
      setStatus('Owner restored successfully.');
      await loadResidents();
    } catch (err) {
      setError('Unable to restore owner. Please try again.');
    } finally {
      setProcessingOwnerId(null);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-slate-700">Resident Directory</h2>
        <p className="text-sm text-slate-500">
          Review homeowner records alongside linked user accounts.
        </p>
      </header>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {status && <p className="text-sm text-green-600">{status}</p>}
      {loading && <p className="text-sm text-slate-500">Loading residents…</p>}

      <section className="overflow-x-auto rounded border border-slate-200">
        <h3 className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
          Active Owner Records
        </h3>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Property</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Primary Owner</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Contact</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Linked Account</th>
              {isSysAdmin && <th className="px-3 py-2 text-left font-medium text-slate-600">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {activeOwnerRows.map((record) => {
              const owner = record.owner!;
              const linkedUser = record.user;
              return (
                <tr key={owner.id}>
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-700">{formatProperty(owner)}</div>
                    <div className="text-xs text-slate-500">{formatOwnerId(owner)}</div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-700">{owner.primary_name}</div>
                    {owner.secondary_name && (
                      <div className="text-xs text-slate-500">Secondary: {owner.secondary_name}</div>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-col">
                      <span>{owner.primary_email ?? 'No email'}</span>
                      {owner.primary_phone && <span>{owner.primary_phone}</span>}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {linkedUser ? (
                      <div className="flex flex-col">
                        <span>{linkedUser.email}</span>
                        <span className="text-xs text-slate-500">{linkedUser.role.name}</span>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-500">No linked login</span>
                    )}
                  </td>
                  {isSysAdmin && (
                    <td className="px-3 py-2 space-x-2">
                      <button
                        type="button"
                        onClick={() => openEdit(owner)}
                        className="rounded bg-slate-600 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-500"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleArchive(owner.id)}
                        className="rounded bg-rose-600 px-3 py-1 text-xs font-semibold text-white hover:bg-rose-500 disabled:opacity-60"
                        disabled={processingOwnerId === owner.id}
                      >
                        {processingOwnerId === owner.id ? 'Archiving…' : 'Archive'}
                      </button>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
        {activeOwnerRows.length === 0 && !loading && (
          <p className="px-3 py-4 text-sm text-slate-500">No owner records found.</p>
        )}
      </section>

      {archivedOwnerRows.length > 0 && (
        <section className="overflow-x-auto rounded border border-slate-200">
          <h3 className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
            Archived Owners
          </h3>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Property</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Primary Owner</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Archived On</th>
                <th className="px-3 py-2 text-left font-medium text-slate-600">Reason</th>
                {isSysAdmin && <th className="px-3 py-2 text-left font-medium text-slate-600">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {archivedOwnerRows.map((record) => {
                const owner = record.owner!;
                return (
                  <tr key={owner.id} className="bg-slate-50">
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-700">{formatProperty(owner)}</div>
                      <div className="text-xs text-slate-500">{formatOwnerId(owner)}</div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="font-medium text-slate-700">{owner.primary_name}</div>
                      {owner.secondary_name && (
                        <div className="text-xs text-slate-500">Secondary: {owner.secondary_name}</div>
                      )}
                    </td>
                    <td className="px-3 py-2">{formatDate(owner.archived_at)}</td>
                    <td className="px-3 py-2">{owner.archived_reason ?? '—'}</td>
                    {isSysAdmin && (
                      <td className="px-3 py-2">
                        <button
                          type="button"
                          onClick={() => void handleRestore(owner.id)}
                          className="rounded bg-emerald-600 px-3 py-1 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
                          disabled={processingOwnerId === owner.id}
                        >
                          {processingOwnerId === owner.id ? 'Restoring…' : 'Restore'}
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      <section className="overflow-x-auto rounded border border-slate-200">
        <h3 className="border-b border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-600">
          User Accounts
        </h3>
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Email</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Name</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Roles</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Owner Record</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Status</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {accountRows.map((record) => {
              const user = record.user!;
              const owner = record.owner;
              const isUnlinked = !owner;
              const created = new Date(user.created_at).toLocaleString();
              return (
                <tr
                  key={user.id}
                  className={
                    isUnlinked
                      ? 'bg-amber-50/60'
                      : !user.is_active
                      ? 'bg-slate-100/80'
                      : undefined
                  }
                >
                  <td className="px-3 py-2">{user.email}</td>
                  <td className="px-3 py-2">{user.full_name ?? '—'}</td>
                  <td className="px-3 py-2">{formatUserRoles(user)}</td>
                  <td className="px-3 py-2">
                    {owner ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
                        {formatOwnerId(owner)}
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-700">
                        Unlinked
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {user.is_active ? (
                      <span className="text-xs font-semibold text-emerald-600">Active</span>
                    ) : (
                      <div className="flex flex-col text-xs text-slate-500">
                        <span className="font-semibold text-slate-600">Inactive</span>
                        {user.archived_reason && <span>{user.archived_reason}</span>}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">{created}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {accountRows.length === 0 && !loading && (
          <p className="px-3 py-4 text-sm text-slate-500">No user accounts found.</p>
        )}
      </section>

      {unlinkedAccounts.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          {unlinkedAccounts.length} user account(s) do not have an owner record yet. Update the matching
          owner contact email or create a new owner record to link them.
        </div>
      )}

      {inactiveAccounts.length > 0 && (
        <div className="rounded border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          {inactiveAccounts.length} account(s) are inactive. Restoring an owner can optionally reactivate
          their login.
        </div>
      )}

      {editingOwner && ownerForm && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/40 px-4 py-6">
          <div className="mx-auto flex min-h-full w-full max-w-3xl items-center justify-center">
            <div className="w-full max-h-[90vh] overflow-y-auto rounded bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-700">Edit Owner</h3>
                <p className="text-xs text-slate-500">{formatProperty(editingOwner)} • {formatOwnerId(editingOwner)}</p>
              </div>
              <button
                type="button"
                onClick={closeEdit}
                className="text-sm text-slate-500 hover:text-slate-700"
              >
                Close
              </button>
            </div>
            <form className="mt-4 space-y-4" onSubmit={handleOwnerSave}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Primary Name</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.primary_name ?? ''}
                    onChange={(e) => handleOwnerFieldChange('primary_name', e.target.value)}
                    required
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Secondary Name</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.secondary_name ?? ''}
                    onChange={(e) => handleOwnerFieldChange('secondary_name', e.target.value)}
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Property Address</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.property_address ?? ''}
                    onChange={(e) => handleOwnerFieldChange('property_address', e.target.value)}
                    required
                    placeholder="123 Main St"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Property Address</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.property_address ?? ''}
                    onChange={(e) => handleOwnerFieldChange('property_address', e.target.value)}
                    required
                    placeholder="123 Main St"
                  />
                </label>
                <label className="sm:col-span-2 text-sm">
                  <span className="mb-1 block text-slate-600">Mailing Address</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.mailing_address ?? ''}
                    onChange={(e) => handleOwnerFieldChange('mailing_address', e.target.value)}
                    placeholder="Optional"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Primary Email</span>
                  <input
                    type="email"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.primary_email ?? ''}
                    onChange={(e) => handleOwnerFieldChange('primary_email', e.target.value)}
                    placeholder="owner@example.com"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Secondary Email</span>
                  <input
                    type="email"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.secondary_email ?? ''}
                    onChange={(e) => handleOwnerFieldChange('secondary_email', e.target.value)}
                    placeholder="Optional"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Primary Phone</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.primary_phone ?? ''}
                    onChange={(e) => handleOwnerFieldChange('primary_phone', e.target.value)}
                    placeholder="555-123-4567"
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Secondary Phone</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.secondary_phone ?? ''}
                    onChange={(e) => handleOwnerFieldChange('secondary_phone', e.target.value)}
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Occupancy Status</span>
                  <select
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.occupancy_status ?? ''}
                    onChange={(e) => handleOwnerFieldChange('occupancy_status', e.target.value)}
                  >
                    <option value="">Select status…</option>
                    <option value="OWNER_OCCUPIED">Owner Occupied</option>
                    <option value="TENANT_OCCUPIED">Tenant Occupied</option>
                    <option value="VACANT">Vacant</option>
                    <option value="UNKNOWN">Unknown</option>
                  </select>
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Emergency Contact</span>
                  <input
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.emergency_contact ?? ''}
                    onChange={(e) => handleOwnerFieldChange('emergency_contact', e.target.value)}
                  />
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={Boolean(ownerForm.is_rental)}
                  onChange={(e) => handleOwnerFieldChange('is_rental', e.target.checked)}
                />
                <span className="text-slate-600">Rental Property</span>
              </label>
            </div>
              <div className="rounded border border-slate-200 p-3">
                <h4 className="text-sm font-semibold text-slate-700">Linked Accounts</h4>
                {linkedAccounts.length === 0 ? (
                  <p className="mt-2 text-xs text-slate-500">No user accounts linked to this owner.</p>
                ) : (
                  <ul className="mt-2 space-y-2 text-sm">
                    {linkedAccounts.map((account) => (
                      <li
                        key={account.id}
                        className="flex items-center justify-between rounded border border-slate-200 px-3 py-2"
                      >
                        <div>
                          <div className="font-medium text-slate-700">{account.email}</div>
                          <div className="text-xs text-slate-500">
                            {account.full_name ?? '—'} • {account.role.name}
                            {account.is_active ? '' : ' • Inactive'}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => void handleUnlinkUser(account.id)}
                          className="text-xs font-semibold text-rose-600 hover:text-rose-500"
                          disabled={linkingUserId === account.id}
                        >
                          {linkingUserId === account.id ? 'Removing…' : 'Remove'}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
                {availableAccounts.length > 0 ? (
                  <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                    <select
                      className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
                      value={selectedLinkUserId}
                      onChange={(e) => setSelectedLinkUserId(e.target.value ? Number(e.target.value) : '')}
                    >
                      <option value="">Select account to link…</option>
                      {availableAccounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.email} • {account.role.name}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => void handleLinkUser()}
                      className="rounded bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
                      disabled={!selectedLinkUserId || linkingUserId !== null}
                    >
                      Link Account
                    </button>
                  </div>
                ) : (
                  <p className="mt-2 text-xs text-slate-500">No additional accounts available for linking.</p>
                )}
              </div>
              <label className="text-sm">
                <span className="mb-1 block text-slate-600">Notes</span>
                <textarea
                  className="w-full rounded border border-slate-300 px-3 py-2"
                  rows={3}
                  value={ownerForm.notesText}
                  onChange={(e) => handleOwnerFieldChange('notesText', e.target.value)}
                  placeholder="Optional notes for board reference"
                />
              </label>
              <div className="flex items-center justify-end gap-3 border-t border-slate-200 pt-4">
                <button
                  type="button"
                  onClick={closeEdit}
                  className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                  disabled={savingOwner}
                >
                  {savingOwner ? 'Saving…' : 'Save Changes'}
                </button>
              </div>
            </form>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OwnersPage;
