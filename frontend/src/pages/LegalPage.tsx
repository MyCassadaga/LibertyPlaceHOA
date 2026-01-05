import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { useAuth } from '../hooks/useAuth';
import { fetchLegalTemplates, sendLegalMessage } from '../services/api';
import { useContractsQuery } from '../features/billing/hooks';
import { Template } from '../types';
import { queryKeys } from '../lib/api/queryKeys';

const LegalPage: React.FC = () => {
  const { user } = useAuth();
  const [contractId, setContractId] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [subject, setSubject] = useState('');
  const [messageBody, setMessageBody] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [confirmSend, setConfirmSend] = useState(false);

  const contractsQuery = useContractsQuery(!!user);
  const templatesQuery = useQuery<Template[]>({
    queryKey: [queryKeys.templates, 'legal'],
    queryFn: fetchLegalTemplates,
  });

  const contracts = contractsQuery.data ?? [];
  const templates = templatesQuery.data ?? [];
  const selectedContract = useMemo(
    () => contracts.find((contract) => contract.id === Number(contractId)) ?? null,
    [contracts, contractId],
  );

  const handleTemplateChange = (selectedId: string) => {
    setTemplateId(selectedId);
    const template = templates.find((item) => item.id === Number(selectedId));
    if (template) {
      setSubject(template.subject);
      setMessageBody(template.body);
    }
  };

  const handleSend = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus(null);
    setError(null);
    if (!contractId) {
      setError('Select a contract before sending.');
      return;
    }
    if (!subject.trim() || !messageBody.trim()) {
      setError('Subject and message are required.');
      return;
    }
    if (!confirmSend) {
      setError('Confirm before sending this legal email.');
      return;
    }
    setSending(true);
    try {
      await sendLegalMessage({
        contract_id: Number(contractId),
        subject: subject.trim(),
        body: messageBody.trim(),
      });
      setStatus('Legal email queued for delivery.');
      setSubject('');
      setMessageBody('');
      setTemplateId('');
      setConfirmSend(false);
    } catch (err) {
      console.error('Unable to send legal email', err);
      setError('Unable to send legal email.');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-semibold text-primary-600">Legal Communications</h2>
        <p className="text-sm text-slate-500">
          Draft and send emails to the association&apos;s legal contract holder from
          legal@libertyplacehoa.com.
        </p>
      </header>

      <section className="rounded border border-slate-200 p-4">
        <h3 className="text-sm font-semibold text-slate-600">Send Legal Message</h3>
        <form className="mt-4 space-y-4" onSubmit={handleSend}>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="legal-contract">
              Contract
            </label>
            <select
              id="legal-contract"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={contractId}
              onChange={(event) => setContractId(event.target.value)}
            >
              <option value="">Select contract…</option>
              {contracts.map((contract) => (
                <option key={contract.id} value={contract.id}>
                  {contract.vendor_name}
                  {contract.service_type ? ` • ${contract.service_type}` : ''}
                </option>
              ))}
            </select>
            {selectedContract?.contact_email && (
              <p className="mt-2 text-xs text-slate-500">Recipient: {selectedContract.contact_email}</p>
            )}
            {selectedContract && !selectedContract.contact_email && (
              <p className="mt-2 text-xs text-rose-600">Add a contact email to this contract before sending.</p>
            )}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="legal-template">
              Template (optional)
            </label>
            <select
              id="legal-template"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm"
              value={templateId}
              onChange={(event) => handleTemplateChange(event.target.value)}
              disabled={templatesQuery.isLoading || templates.length === 0}
            >
              <option value="">No template</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="legal-subject">
              Subject
            </label>
            <input
              id="legal-subject"
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-600" htmlFor="legal-body">
              Message
            </label>
            <textarea
              id="legal-body"
              rows={6}
              className="w-full rounded border border-slate-300 px-3 py-2"
              value={messageBody}
              onChange={(event) => setMessageBody(event.target.value)}
              required
            />
          </div>

          <label className="flex items-start gap-3 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
            <input
              type="checkbox"
              className="mt-1"
              checked={confirmSend}
              onChange={(event) => setConfirmSend(event.target.checked)}
              required
            />
            <span>
              Confirm that this email is ready to send to the legal contact for the selected contract.
            </span>
          </label>

          {status && <p className="text-sm text-emerald-600">{status}</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            className="rounded bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-500 disabled:opacity-60"
            disabled={sending}
          >
            {sending ? 'Sending…' : 'Send legal email'}
          </button>
        </form>
      </section>
    </div>
  );
};

export default LegalPage;
