import React, { useEffect, useMemo, useState } from 'react';
import type { AxiosError } from 'axios';
import QRCode from 'react-qr-code';

import { useAuth } from '../hooks/useAuth';
import {
  changePassword,
  fetchMyOwnerRecord,
  startTwoFactorSetup,
  enableTwoFactor,
  disableTwoFactor,
  updateMyOwnerRecord,
  updateUserProfile,
} from '../services/api';
import { Owner, OwnerSelfUpdatePayload, TwoFactorSetupResponse } from '../types';
import { formatUserRoles } from '../utils/roles';

type OwnerFormState = {
  primary_name: string;
  secondary_name: string;
  property_address: string;
  mailing_address: string;
  primary_phone: string;
  secondary_phone: string;
  emergency_contact: string;
  notes: string;
};

const createOwnerFormState = (record?: Owner | null): OwnerFormState => ({
  primary_name: record?.primary_name ?? '',
  secondary_name: record?.secondary_name ?? '',
  property_address: record?.property_address ?? '',
  mailing_address: record?.mailing_address ?? '',
  primary_phone: record?.primary_phone ?? '',
  secondary_phone: record?.secondary_phone ?? '',
  emergency_contact: record?.emergency_contact ?? '',
  notes: record?.notes ?? '',
});

const OwnerProfilePage: React.FC = () => {
  const { user, refresh } = useAuth();
  const [owner, setOwner] = useState<Owner | null>(null);
  const [ownerMissing, setOwnerMissing] = useState(false);
  const [ownerLoading, setOwnerLoading] = useState(false);

  const [accountForm, setAccountForm] = useState({ full_name: '', email: '', current_password: '' });
  const [accountStatus, setAccountStatus] = useState<string | null>(null);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [accountSaving, setAccountSaving] = useState(false);

  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' });
  const [passwordStatus, setPasswordStatus] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaving, setPasswordSaving] = useState(false);

  const [twoFactorSetup, setTwoFactorSetup] = useState<TwoFactorSetupResponse | null>(null);
  const [twoFactorOtp, setTwoFactorOtp] = useState('');
  const [twoFactorDisableOtp, setTwoFactorDisableOtp] = useState('');
  const [twoFactorStatus, setTwoFactorStatus] = useState<string | null>(null);
  const [twoFactorError, setTwoFactorError] = useState<string | null>(null);
  const [twoFactorLoading, setTwoFactorLoading] = useState(false);

  const [ownerForm, setOwnerForm] = useState<OwnerFormState>(() => createOwnerFormState());
  const [ownerStatus, setOwnerStatus] = useState<string | null>(null);
  const [ownerError, setOwnerError] = useState<string | null>(null);
  const [ownerSaving, setOwnerSaving] = useState(false);

  useEffect(() => {
    if (!user) return;
    setAccountForm({
      full_name: user.full_name ?? '',
      email: user.email,
      current_password: '',
    });
  }, [user]);

  useEffect(() => {
    const loadOwner = async () => {
      if (!user) return;
      setOwnerLoading(true);
      setOwnerMissing(false);
      setOwnerError(null);
      try {
        const record = await fetchMyOwnerRecord();
        setOwner(record);
        setOwnerForm(createOwnerFormState(record));
      } catch (err) {
        const axiosError = err as AxiosError<{ detail?: string }>;
        if (axiosError?.response?.status === 404) {
          setOwner(null);
          setOwnerMissing(true);
        } else {
          console.error('Unable to load owner profile', err);
          setOwnerError('Unable to load owner profile.');
        }
      } finally {
        setOwnerLoading(false);
      }
    };

    void loadOwner();
  }, [user]);

  const formattedTwoFactorSecret = useMemo(() => {
    if (!twoFactorSetup?.secret) {
      return '';
    }
    return twoFactorSetup.secret.replace(/(.{4})/g, '$1 ').trim();
  }, [twoFactorSetup]);

  if (!user) {
    return null;
  }

  const handleAccountInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setAccountForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleOwnerInputChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const { name, value } = event.target;
    setOwnerForm((prev) => ({ ...prev, [name]: value }));
  };

  const handlePasswordInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = event.target;
    setPasswordForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleStartTwoFactor = async () => {
    setTwoFactorStatus(null);
    setTwoFactorError(null);
    setTwoFactorLoading(true);
    try {
      const setup = await startTwoFactorSetup();
      setTwoFactorSetup(setup);
      setTwoFactorStatus('Scan the QR link or enter the secret in your authenticator, then enter the 6-digit code to enable.');
    } catch (err) {
      console.error('2FA setup failed', err);
      setTwoFactorError('Unable to generate a two-factor setup code.');
    } finally {
      setTwoFactorLoading(false);
    }
  };

  const handleEnableTwoFactor = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!twoFactorOtp.trim()) {
      setTwoFactorError('Enter the 6-digit code from your authenticator app.');
      return;
    }
    if (!/^\d{6}$/.test(twoFactorOtp.trim())) {
      setTwoFactorError('Two-factor codes must be exactly 6 digits.');
      return;
    }
    setTwoFactorLoading(true);
    setTwoFactorStatus(null);
    setTwoFactorError(null);
    try {
      await enableTwoFactor(twoFactorOtp.trim());
      await refresh();
      setTwoFactorSetup(null);
      setTwoFactorOtp('');
      setTwoFactorStatus('Two-factor authentication enabled.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to enable two-factor authentication.';
      setTwoFactorError(message);
    } finally {
      setTwoFactorLoading(false);
    }
  };

  const handleDisableTwoFactor = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!twoFactorDisableOtp.trim()) {
      setTwoFactorError('Enter your current 2FA code to disable.');
      return;
    }
    if (!/^\d{6}$/.test(twoFactorDisableOtp.trim())) {
      setTwoFactorError('Two-factor codes must be exactly 6 digits.');
      return;
    }
    setTwoFactorLoading(true);
    setTwoFactorStatus(null);
    setTwoFactorError(null);
    try {
      await disableTwoFactor(twoFactorDisableOtp.trim());
      await refresh();
      setTwoFactorDisableOtp('');
      setTwoFactorStatus('Two-factor authentication disabled.');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to disable two-factor authentication.';
      setTwoFactorError(message);
    } finally {
      setTwoFactorLoading(false);
    }
  };

  const handleAccountSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!user) return;
    setAccountStatus(null);
    setAccountError(null);

    const payload: { full_name?: string | null; email?: string; current_password?: string } = {};
    const fullNameTrimmed = accountForm.full_name.trim();
    const originalFullName = user.full_name ?? '';
    if (fullNameTrimmed !== originalFullName) {
      payload.full_name = fullNameTrimmed.length > 0 ? fullNameTrimmed : null;
    }

    const emailTrimmed = accountForm.email.trim();
    if (emailTrimmed !== user.email) {
      payload.email = emailTrimmed;
      if (!accountForm.current_password) {
        setAccountError('Enter your current password to change email.');
        return;
      }
      payload.current_password = accountForm.current_password;
    } else if (accountForm.current_password) {
      payload.current_password = accountForm.current_password;
    }

    if (Object.keys(payload).length === 0) {
      setAccountStatus('No changes to save.');
      return;
    }

    setAccountSaving(true);
    try {
      const updatedUser = await updateUserProfile(payload);
      await refresh();
      setAccountStatus('Account details updated.');
      setAccountForm({
        full_name: updatedUser.full_name ?? '',
        email: updatedUser.email,
        current_password: '',
      });

      if (owner && payload.email) {
        try {
          const updatedOwner = await updateMyOwnerRecord({ primary_email: payload.email });
          setOwner(updatedOwner);
          setOwnerForm(createOwnerFormState(updatedOwner));
        } catch (syncError) {
          console.error('Failed to sync owner email', syncError);
        }
      }
    } catch (err) {
      const axiosError = err as { response?: { data?: { detail?: string } } };
      const detail = axiosError.response?.data?.detail;
      setAccountError(detail ?? 'Unable to update account settings.');
    } finally {
      setAccountSaving(false);
    }
  };

  const handlePasswordSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setPasswordStatus(null);
    setPasswordError(null);

    if (passwordForm.next.length < 8) {
      setPasswordError('New password must be at least 8 characters.');
      return;
    }
    if (passwordForm.next !== passwordForm.confirm) {
      setPasswordError('New password and confirmation do not match.');
      return;
    }

    setPasswordSaving(true);
    try {
      await changePassword({ current_password: passwordForm.current, new_password: passwordForm.next });
      setPasswordStatus('Password updated successfully.');
      setPasswordForm({ current: '', next: '', confirm: '' });
    } catch (err) {
      console.error('Unable to update password', err);
      setPasswordError('Unable to update password. Check your current password and try again.');
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleOwnerSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!owner) {
      return;
    }
    setOwnerStatus(null);
    setOwnerError(null);

    const fields: (keyof OwnerFormState)[] = [
      'primary_name',
      'secondary_name',
      'property_address',
      'mailing_address',
      'primary_phone',
      'secondary_phone',
      'emergency_contact',
      'notes',
    ];

    const changes: Partial<OwnerSelfUpdatePayload> = {};

    fields.forEach((field) => {
      const currentValue = owner[field] ?? '';
      const nextValue = ownerForm[field] ?? '';
      if (currentValue !== nextValue) {
        const trimmed = field === 'notes' ? nextValue : nextValue.trim();
        changes[field] = trimmed.length > 0 ? trimmed : null;
      }
    });

    if (Object.keys(changes).length === 0) {
      setOwnerStatus('No changes to save.');
      return;
    }

    setOwnerSaving(true);
    try {
      const updatedOwner = await updateMyOwnerRecord(changes as OwnerSelfUpdatePayload);
      setOwner(updatedOwner);
      setOwnerForm(createOwnerFormState(updatedOwner));
      setOwnerStatus('Owner profile updated.');
    } catch (err) {
      console.error('Unable to update owner profile', err);
      setOwnerError('Unable to update owner profile.');
    } finally {
      setOwnerSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h2 className="text-xl font-semibold text-slate-700">Account &amp; Profile</h2>
        <p className="text-sm text-slate-500">
          Signed in as {user.email} • Roles: {formatUserRoles(user)}
        </p>
      </header>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Account Details</h3>
        <p className="mb-4 text-sm text-slate-500">
          Update your name or email. Changing your email requires your current password.
        </p>
        <form className="space-y-4" onSubmit={handleAccountSubmit}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Full Name</span>
              <input
                name="full_name"
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={accountForm.full_name}
                onChange={handleAccountInputChange}
                placeholder="Optional"
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Email</span>
              <input
                name="email"
                type="email"
                className="w-full rounded border border-slate-300 px-3 py-2"
                required
                value={accountForm.email}
                onChange={handleAccountInputChange}
              />
            </label>
            <label className="sm:col-span-2 text-sm">
              <span className="mb-1 block text-slate-600">Current Password</span>
              <input
                name="current_password"
                type="password"
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={accountForm.current_password}
                onChange={handleAccountInputChange}
                placeholder="Required when changing email"
                minLength={8}
              />
            </label>
          </div>
          {accountStatus && <p className="text-sm text-green-600">{accountStatus}</p>}
          {accountError && <p className="text-sm text-red-600">{accountError}</p>}
          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:opacity-60"
            disabled={accountSaving}
          >
            {accountSaving ? 'Saving…' : 'Save Changes'}
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Change Password</h3>
        <p className="mb-4 text-sm text-slate-500">Choose a strong password of at least eight characters.</p>
        <form className="space-y-4" onSubmit={handlePasswordSubmit}>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Current Password</span>
              <input
                name="current"
                type="password"
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={passwordForm.current}
                onChange={handlePasswordInputChange}
                required
                minLength={8}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">New Password</span>
              <input
                name="next"
                type="password"
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={passwordForm.next}
                onChange={handlePasswordInputChange}
                required
                minLength={8}
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block text-slate-600">Confirm Password</span>
              <input
                name="confirm"
                type="password"
                className="w-full rounded border border-slate-300 px-3 py-2"
                value={passwordForm.confirm}
                onChange={handlePasswordInputChange}
                required
                minLength={8}
              />
            </label>
          </div>
          {passwordStatus && <p className="text-sm text-green-600">{passwordStatus}</p>}
          {passwordError && <p className="text-sm text-red-600">{passwordError}</p>}
          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:opacity-60"
            disabled={passwordSaving}
          >
            {passwordSaving ? 'Updating…' : 'Update Password'}
          </button>
        </form>
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Two-Factor Authentication</h3>
        <p className="mb-3 text-sm text-slate-500">
          Protect your account with a rotating 6-digit code from an authenticator app in addition to your password.
        </p>
        {twoFactorStatus && <p className="text-sm text-emerald-600">{twoFactorStatus}</p>}
        {twoFactorError && <p className="text-sm text-red-600">{twoFactorError}</p>}
        {user.two_factor_enabled ? (
          <form className="mt-4 space-y-3" onSubmit={handleDisableTwoFactor}>
            <label className="text-sm text-slate-600" htmlFor="disable-otp">
              Enter your current 2FA code to disable
            </label>
            <input
              id="disable-otp"
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              className="w-full rounded border border-slate-300 px-3 py-2"
              placeholder="123456"
              value={twoFactorDisableOtp}
              onChange={(event) => setTwoFactorDisableOtp(event.target.value)}
              required
            />
            <div className="flex justify-end">
              <button
                type="submit"
                className="rounded bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-500 disabled:opacity-60"
                disabled={twoFactorLoading}
              >
                {twoFactorLoading ? 'Disabling…' : 'Disable 2FA'}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-4">
            {twoFactorSetup ? (
              <div className="space-y-3 rounded border border-slate-200 p-3">
                <p className="text-sm text-slate-600">
                  Scan the QR link or enter the secret below into Google Authenticator, 1Password, or a compatible app.
                </p>
                <div className="flex flex-col items-center gap-3">
                  <QRCode value={twoFactorSetup.otpauth_url} size={168} />
                  <p className="w-full rounded bg-slate-100 px-3 py-2 font-mono text-sm text-center tracking-widest">
                    {formattedTwoFactorSecret}
                  </p>
                </div>
                <a
                  href={twoFactorSetup.otpauth_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-semibold text-primary-600 hover:text-primary-500"
                >
                  Open in authenticator app
                </a>
                <form className="space-y-3" onSubmit={handleEnableTwoFactor}>
                  <label className="text-sm text-slate-600" htmlFor="enable-otp">
                    Enter the current 6-digit code from your authenticator
                  </label>
                  <input
                    id="enable-otp"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    placeholder="123456"
                    value={twoFactorOtp}
                    onChange={(event) => setTwoFactorOtp(event.target.value)}
                    required
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      className="rounded border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                      onClick={() => {
                        setTwoFactorSetup(null);
                        setTwoFactorOtp('');
                      }}
                      disabled={twoFactorLoading}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                      disabled={twoFactorLoading}
                    >
                      {twoFactorLoading ? 'Verifying…' : 'Enable 2FA'}
                    </button>
                  </div>
                </form>
              </div>
            ) : (
              <button
                type="button"
                className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
                onClick={handleStartTwoFactor}
                disabled={twoFactorLoading}
              >
                {twoFactorLoading ? 'Preparing…' : 'Generate Setup Code'}
              </button>
            )}
          </div>
        )}
      </section>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-lg font-semibold text-slate-700">Owner Contact Details</h3>
        {ownerLoading ? (
          <p className="text-sm text-slate-500">Loading owner profile…</p>
        ) : owner ? (
          <>
            <p className="mb-4 text-sm text-slate-500">
              Property address: {owner.property_address}
            </p>
            <form className="space-y-4" onSubmit={handleOwnerSubmit}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Primary Owner</span>
                  <input
                    name="primary_name"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.primary_name}
                    onChange={handleOwnerInputChange}
                    required
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Secondary Owner</span>
                  <input
                    name="secondary_name"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.secondary_name}
                    onChange={handleOwnerInputChange}
                  />
                </label>
                <label className="text-sm sm:col-span-2">
                  <span className="mb-1 block text-slate-600">Property Address</span>
                  <input
                    name="property_address"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.property_address}
                    onChange={handleOwnerInputChange}
                    required
                  />
                </label>
                <label className="text-sm sm:col-span-2">
                  <span className="mb-1 block text-slate-600">Mailing Address</span>
                  <input
                    name="mailing_address"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.mailing_address}
                    onChange={handleOwnerInputChange}
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Primary Phone</span>
                  <input
                    name="primary_phone"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.primary_phone}
                    onChange={handleOwnerInputChange}
                  />
                </label>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Secondary Phone</span>
                  <input
                    name="secondary_phone"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.secondary_phone}
                    onChange={handleOwnerInputChange}
                  />
                </label>
                <label className="text-sm sm:col-span-2">
                  <span className="mb-1 block text-slate-600">Emergency Contact</span>
                  <input
                    name="emergency_contact"
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.emergency_contact}
                    onChange={handleOwnerInputChange}
                  />
                </label>
                <label className="text-sm sm:col-span-2">
                  <span className="mb-1 block text-slate-600">Notes</span>
                  <textarea
                    name="notes"
                    rows={3}
                    className="w-full rounded border border-slate-300 px-3 py-2"
                    value={ownerForm.notes}
                    onChange={handleOwnerInputChange}
                  />
                </label>
              </div>
              {ownerStatus && <p className="text-sm text-green-600">{ownerStatus}</p>}
              {ownerError && <p className="text-sm text-red-600">{ownerError}</p>}
              <button
                type="submit"
                className="rounded bg-primary-600 px-4 py-2 text-white hover:bg-primary-500 disabled:opacity-60"
                disabled={ownerSaving}
              >
                {ownerSaving ? 'Saving…' : 'Save Owner Details'}
              </button>
            </form>
          </>
        ) : ownerMissing ? (
          <p className="text-sm text-slate-500">
            No owner record is linked to this account yet. Create an owner record from the Owners page or contact the
            board to attach this login to a lot.
          </p>
        ) : (
          <p className="text-sm text-red-600">Owner profile unavailable.</p>
        )}
      </section>
    </div>
  );
};

export default OwnerProfilePage;
