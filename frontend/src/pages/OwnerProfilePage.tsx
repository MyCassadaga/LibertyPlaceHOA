import React, { useEffect, useMemo, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { fetchMyOwnerRecord, submitOwnerUpdateProposal } from '../services/api';
import { Owner } from '../types';

type EditableField = 'mailing_address' | 'primary_phone' | 'secondary_phone' | 'notes';

const editableFields: EditableField[] = ['mailing_address', 'primary_phone', 'secondary_phone', 'notes'];

const OwnerProfilePage: React.FC = () => {
  const { user } = useAuth();
  const [owner, setOwner] = useState<Owner | null>(null);
  const [formState, setFormState] = useState<Record<EditableField, string>>({
    mailing_address: '',
    primary_phone: '',
    secondary_phone: '',
    notes: '',
  });
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!user) return;
      if (user.role.name !== 'HOMEOWNER') {
        setStatus('Owner profiles are read-only for board members. Use the Owners page to manage records.');
        return;
      }
      try {
        const record = await fetchMyOwnerRecord();
        setOwner(record);
        setFormState({
          mailing_address: record.mailing_address ?? '',
          primary_phone: record.primary_phone ?? '',
          secondary_phone: record.secondary_phone ?? '',
          notes: record.notes ?? '',
        });
      } catch (err) {
        setError('Unable to load your owner record.');
      }
    };

    load();
  }, [user]);

  const hasChanges = useMemo(() => {
    if (!owner) return false;
    return editableFields.some((field) => {
      const originalValue = owner[field] ?? '';
      const currentValue = formState[field] ?? '';
      return originalValue !== currentValue;
    });
  }, [owner, formState]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!owner) return;
    if (!hasChanges) {
      setStatus('No changes to submit.');
      return;
    }
    try {
      const proposedChanges: Record<string, string> = {};
      editableFields.forEach((field) => {
        const originalValue = owner[field] ?? '';
        const currentValue = formState[field] ?? '';
        if (originalValue !== currentValue) {
          proposedChanges[field] = currentValue;
        }
      });
      await submitOwnerUpdateProposal(owner.id, proposedChanges);
      setStatus('Submitted update request for board review.');
      setError(null);
    } catch (err) {
      setError('Unable to submit update request.');
    }
  };

  if (!user) return null;

  if (user.role.name !== 'HOMEOWNER') {
    return (
      <div>
        <h2 className="text-xl font-semibold text-slate-700">Owner Profile</h2>
        <p className="mt-4 text-sm text-slate-500">{status}</p>
      </div>
    );
  }

  if (!owner) {
    return <p className="text-sm text-slate-500">Loading owner profile…</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-slate-700">Your Owner Profile</h2>
        <p className="text-sm text-slate-500">Lot {owner.lot} • {owner.property_address}</p>
      </header>
      <div className="rounded border border-slate-200 p-4">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-sm">
          <div>
            <dt className="text-slate-500">Primary Owner</dt>
            <dd className="font-medium text-slate-700">{owner.primary_name}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Primary Email</dt>
            <dd className="font-medium text-slate-700">{owner.primary_email ?? 'Not provided'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Secondary Owner</dt>
            <dd className="font-medium text-slate-700">{owner.secondary_name ?? '—'}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Emergency Contact</dt>
            <dd className="font-medium text-slate-700">{owner.emergency_contact ?? '—'}</dd>
          </div>
        </dl>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Request Contact Updates</h3>
        <p className="text-sm text-slate-500">
          Submit changes for the board to review. Updates are not immediate until approved.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <label className="text-sm">
            <span className="mb-1 block text-slate-600">Mailing Address</span>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={formState.mailing_address ?? ''}
              onChange={(event) => setFormState((prev) => ({ ...prev, mailing_address: event.target.value }))}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-slate-600">Primary Phone</span>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={formState.primary_phone ?? ''}
              onChange={(event) => setFormState((prev) => ({ ...prev, primary_phone: event.target.value }))}
            />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-slate-600">Secondary Phone</span>
            <input
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={formState.secondary_phone ?? ''}
              onChange={(event) => setFormState((prev) => ({ ...prev, secondary_phone: event.target.value }))}
            />
          </label>
          <label className="sm:col-span-2 text-sm">
            <span className="mb-1 block text-slate-600">Notes</span>
            <textarea
              className="w-full rounded border border-slate-300 px-3 py-2"
              rows={3}
              value={formState.notes ?? ''}
              onChange={(event) => setFormState((prev) => ({ ...prev, notes: event.target.value }))}
            />
          </label>
        </div>
        {status && <p className="text-sm text-green-600">{status}</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:opacity-60"
          disabled={!hasChanges}
        >
          Submit for Review
        </button>
      </form>
    </div>
  );
};

export default OwnerProfilePage;
