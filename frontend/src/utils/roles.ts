import { User } from '../types';

export const getPrimaryRoleName = (user: User | null | undefined): string | null => {
  if (!user) {
    return null;
  }
  if (user.primary_role) {
    return user.primary_role.name;
  }
  if (user.role) {
    return user.role.name;
  }
  if (user.roles && user.roles.length > 0) {
    return user.roles[0].name;
  }
  return null;
};

export const userHasRole = (user: User | null | undefined, roleName: string): boolean => {
  if (!user) {
    return false;
  }
  const normalized = roleName.toUpperCase();
  if (user.primary_role && user.primary_role.name.toUpperCase() === normalized) {
    return true;
  }
  if (user.role && user.role.name.toUpperCase() === normalized) {
    return true;
  }
  return user.roles?.some((role) => role.name.toUpperCase() === normalized) ?? false;
};

export const userHasAnyRole = (user: User | null | undefined, roleNames: string[]): boolean => {
  if (!user || roleNames.length === 0) {
    return false;
  }
  const normalized = roleNames.map((role) => role.toUpperCase());
  return normalized.some((role) => userHasRole(user, role));
};

export const formatUserRoles = (user: User | null | undefined): string => {
  if (!user) {
    return '';
  }
  const names = new Set<string>();
  if (user.primary_role) {
    names.add(user.primary_role.name);
  }
  if (user.role) {
    names.add(user.role.name);
  }
  user.roles?.forEach((role) => names.add(role.name));
  const list = Array.from(names);
  if (list.length === 0) {
    return 'No Role';
  }
  return list.join(', ');
};
