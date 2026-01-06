import React from 'react';
import clsx from 'clsx';

type TableContainerProps = {
  children: React.ReactNode;
  className?: string;
};

const TableContainer: React.FC<TableContainerProps> = ({ children, className }) => (
  <div className={clsx('w-full overflow-x-auto', className)}>{children}</div>
);

export default TableContainer;
