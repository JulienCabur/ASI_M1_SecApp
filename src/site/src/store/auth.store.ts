import { create } from 'zustand';
import type { User, Role } from '@/types';

interface AuthStoreState {
  user: User | null;
  isAuthenticated: boolean;
  role: Role | null;
  setUser: (user: User) => void;
  clear: () => void;
}

/**
 * Store d'auth : ne contient AUCUN token (BFF). Les tokens vivent dans le
 * cookie httpOnly côté serveur ; ici on ne stocke que le profil utilisateur
 * dérivé de `/auth/me`.
 */
export const useAuthStore = create<AuthStoreState>((set) => ({
  user: null,
  isAuthenticated: false,
  role: null,

  setUser: (user) =>
    set({
      user,
      isAuthenticated: true,
      role: user.role,
    }),

  clear: () =>
    set({
      user: null,
      isAuthenticated: false,
      role: null,
    }),
}));
