import { create } from 'zustand';
import type { User, Role } from '@/types';

interface AuthStoreState {
  user: User | null;
  isAuthenticated: boolean;
  role: Role | null;
  token: string | null;
  setUser: (user: User, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStoreState>((set) => ({
  user: null,
  isAuthenticated: false,
  role: null,
  token: null,

  setUser: (user, token) =>
    set({
      user,
      token,
      isAuthenticated: true,
      role: user.role,
    }),

  logout: () => {
    // Actual keycloak.logout() is called from the service layer to avoid circular deps
    set({
      user: null,
      isAuthenticated: false,
      role: null,
      token: null,
    });
  },
}));
