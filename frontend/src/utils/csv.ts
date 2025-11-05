export interface CsvColumn<T> {
  header: string;
  accessor: (row: T) => string | number | null | undefined;
}

export const downloadCsvFromData = <T extends object>(filename: string, rows: T[], columns: CsvColumn<T>[]): void => {
  if (!rows.length) {
    return;
  }
  const escape = (value: string | number | null | undefined): string => {
    if (value === null || value === undefined) return '';
    const stringValue = String(value).replace(/\r?\n/g, ' ');
    if (stringValue.includes('"') || stringValue.includes(',') || stringValue.includes('\n')) {
      return `"${stringValue.replace(/"/g, '""')}"`;
    }
    return stringValue;
  };

  const header = columns.map((column) => escape(column.header)).join(',');
  const lines = rows.map((row) => columns.map((column) => escape(column.accessor(row))).join(','));
  const csvContent = [header, ...lines].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};
