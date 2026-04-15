import { useAuthStore } from '@/store/auth.store';

export const useAuth = () => {
  const { user, isAuthenticated, role, token, setUser, logout } = useAuthStore();
  return { user, isAuthenticated, role, token, setUser, logout };
};
