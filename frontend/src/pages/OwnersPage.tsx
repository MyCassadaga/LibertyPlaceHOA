import React, { useEffect, useState } from 'react';

import { fetchOwners } from '../services/api';
import { Owner } from '../types';

const OwnersPage: React.FC = () => {
  const [owners, setOwners] = useState<Owner[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await fetchOwners();
        setOwners(data);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold text-slate-700">Homeowner Directory</h2>
      {loading && <p className="text-sm text-slate-500">Loading owners…</p>}
      <div className="overflow-x-auto rounded border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Lot</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Primary Owner</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Contact</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">Occupancy</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {owners.map((owner) => (
              <tr key={owner.id}>
                <td className="px-3 py-2">{owner.lot}</td>
                <td className="px-3 py-2">{owner.primary_name}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-col">
                    <span>{owner.primary_email ?? 'No email'}</span>
                    {owner.primary_phone && <span>{owner.primary_phone}</span>}
                  </div>
                </td>
                <td className="px-3 py-2">{owner.occupancy_status ?? 'Unknown'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {owners.length === 0 && !loading && (
          <p className="px-3 py-4 text-sm text-slate-500">No owners on file.</p>
        )}
      </div>
    </div>
  );
};

export default OwnersPage;
