import React, { useMemo, useState } from 'react';

type SortDirection = 'asc' | 'desc';
type SortableValue = string | number | Date | boolean | null | undefined;

export interface SortableColumn<T> {
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortValue?: (row: T) => SortableValue;
  align?: 'left' | 'right' | 'center';
}

interface SortableTableProps<T> {
  columns: SortableColumn<T>[];
  data: T[];
  emptyMessage?: string;
}

const getComparableValue = (value: SortableValue): number | string | null => {
  if (value instanceof Date) {
    return value.getTime();
  }
  if (typeof value === 'number' || typeof value === 'string') {
    return value;
  }
  if (value == null) {
    return null;
  }
  return value.toString();
};

const SortableTable = <T extends object>({ columns, data, emptyMessage = 'No records found.' }: SortableTableProps<T>) => {
  const [sortIndex, setSortIndex] = useState<number | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');

  const sortedData = useMemo(() => {
    if (sortIndex === null) {
      return data;
    }

    const column = columns[sortIndex];
    if (!column) {
      return data;
    }

    const extractor: (row: T) => SortableValue =
      column.sortValue ?? ((row: T) => column.accessor(row) as SortableValue);

    const sorted = [...data].sort((a, b) => {
      const aValue = getComparableValue(extractor(a));
      const bValue = getComparableValue(extractor(b));

      if (aValue === bValue) return 0;
      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;

      if (typeof aValue === 'number' && typeof bValue === 'number') {
        return aValue - bValue;
      }

      return String(aValue).localeCompare(String(bValue));
    });

    return sortDirection === 'asc' ? sorted : sorted.reverse();
  }, [columns, data, sortDirection, sortIndex]);

  if (!sortedData.length) {
    return <p className="text-sm text-slate-500">{emptyMessage}</p>;
  }

  const handleSort = (columnIndex: number) => {
    if (sortIndex === columnIndex) {
      setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortIndex(columnIndex);
      setSortDirection('asc');
    }
  };

  return (
    <div className="overflow-x-auto rounded border border-slate-200">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            {columns.map((column, index) => {
              const isSorted = index === sortIndex;
              return (
                <th
                  key={column.header}
                  scope="col"
                  className={`cursor-pointer px-3 py-2 text-left font-semibold text-slate-600`}
                  onClick={() => handleSort(index)}
                >
                  <span className="inline-flex items-center gap-1">
                    {column.header}
                    {isSorted && (
                      <span aria-hidden="true">{sortDirection === 'asc' ? '▲' : '▼'}</span>
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sortedData.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column, columnIndex) => (
                <td
                  key={`${rowIndex}-${columnIndex}`}
                  className={`px-3 py-2 text-slate-700 ${column.align === 'right' ? 'text-right' : column.align === 'center' ? 'text-center' : 'text-left'}`}
                >
                  {column.accessor(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default SortableTable;
