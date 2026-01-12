import React from 'react';

import { TemplateType } from '../../types';

interface TemplateDefinitionsTableProps {
  templateTypes: TemplateType[];
  isLoading: boolean;
  isError: boolean;
}

const TemplateDefinitionsTable: React.FC<TemplateDefinitionsTableProps> = ({
  templateTypes,
  isLoading,
  isError,
}) => {
  if (isLoading) {
    return <p className="text-sm text-slate-500">Loading template definitions...</p>;
  }

  if (isError) {
    return <p className="text-sm text-red-600">Unable to load template definitions.</p>;
  }

  if (templateTypes.length === 0) {
    return <p className="text-sm text-slate-500">No template definitions available.</p>;
  }

  return (
    <div className="overflow-hidden rounded border border-slate-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2">Name</th>
            <th className="px-3 py-2">Definition</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-200">
          {templateTypes.map((templateType) => (
            <tr key={templateType.key} className="align-top">
              <td className="px-3 py-2 font-semibold text-slate-700">{templateType.label}</td>
              <td className="px-3 py-2 text-slate-600">{templateType.definition}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default TemplateDefinitionsTable;
