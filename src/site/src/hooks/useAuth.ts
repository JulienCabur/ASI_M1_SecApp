import { useAuthStore } from '@/store/auth.store';

export const useAuth = () => {
  const { user, isAuthenticated, role, setUser, clear } = useAuthStore();
  return { user, isAuthenticated, role, setUser, clear };
};
