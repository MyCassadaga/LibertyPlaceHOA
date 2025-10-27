import React, { useEffect, useState } from 'react';

import { fetchContracts } from '../services/api';
import { Contract } from '../types';

const ContractsPage: React.FC = () => {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchContracts();
        setContracts(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-700">Vendor Contracts</h2>
      {loading && <p className="text-sm text-slate-500">Loading contracts…</p>}
      <div className="overflow-x-auto rounded border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Vendor</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Service</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Start</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">End</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Auto Renew</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {contracts.map((contract) => (
              <tr key={contract.id}>
                <td className="px-3 py-2">{contract.vendor_name}</td>
                <td className="px-3 py-2">{contract.service_type ?? '—'}</td>
                <td className="px-3 py-2">{new Date(contract.start_date).toLocaleDateString()}</td>
                <td className="px-3 py-2">{contract.end_date ? new Date(contract.end_date).toLocaleDateString() : 'Open'}</td>
                <td className="px-3 py-2">{contract.auto_renew ? 'Yes' : 'No'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {contracts.length === 0 && !loading && (
          <p className="px-3 py-4 text-sm text-slate-500">No contracts recorded yet.</p>
        )}
      </div>
    </div>
  );
};

export default ContractsPage;
