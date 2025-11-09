import React, { useEffect, useState } from 'react';
import { Location, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { API_BASE_URL, fetchLoginBackground } from '../services/api';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, loading } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [backgroundUrl, setBackgroundUrl] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const loadBackground = async () => {
      try {
        const data = await fetchLoginBackground();
        if (!isMounted) return;
        if (data.url) {
          const trimmed = data.url.trim();
          if (/^https?:\/\//i.test(trimmed)) {
            setBackgroundUrl(trimmed);
          } else {
            const base = API_BASE_URL.replace(/\/$/, '');
            const path = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
            setBackgroundUrl(`${base}${path}`);
          }
        } else {
          setBackgroundUrl(null);
        }
      } catch {
        if (isMounted) {
          setBackgroundUrl(null);
        }
      }
    };
    void loadBackground();
    return () => {
      isMounted = false;
    };
  }, []);

  const from = (location.state as { from?: Location })?.from?.pathname || '/dashboard';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      setError(null);
      const trimmedOtp = otp.trim();
      if (trimmedOtp && !/^\d{6}$/.test(trimmedOtp)) {
        setError('Two-factor codes must be exactly 6 digits.');
        return;
      }
      await login(email, password, trimmedOtp || undefined);
      navigate(from, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to sign in. Please try again.';
      setError(message);
    }
  };

  const containerStyle = backgroundUrl
    ? {
        backgroundImage: `url(${backgroundUrl})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }
    : undefined;

  return (
    <div
      className="min-h-screen bg-slate-100"
      style={containerStyle}
    >
      <div className="flex min-h-screen items-center justify-center bg-slate-900/40 p-6">
        <div
          className="w-full max-w-md rounded-xl p-8 shadow-2xl backdrop-blur-md"
          style={{ backgroundColor: 'rgba(255,255,255,0.85)' }}
        >
          <h1 className="mb-6 text-center text-2xl font-semibold text-primary-600">
            Liberty Place HOA Portal
          </h1>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="w-full rounded border border-slate-300 px-3 py-2 focus:border-primary-500 focus:outline-none"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="w-full rounded border border-slate-300 px-3 py-2 focus:border-primary-500 focus:outline-none"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="otp">
                Two-Factor Code (if enabled)
              </label>
              <input
                id="otp"
                type="text"
                inputMode="numeric"
                maxLength={6}
                className="w-full rounded border border-slate-300 px-3 py-2 focus:border-primary-500 focus:outline-none"
                value={otp}
                onChange={(event) => setOtp(event.target.value)}
                placeholder="123456"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              className="w-full rounded bg-primary-600 py-2 text-white hover:bg-primary-500 disabled:opacity-60"
              disabled={loading}
            >
              {loading ? 'Signing in…' : 'Sign In'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
