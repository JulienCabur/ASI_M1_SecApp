import { create } from 'zustand';

/**
 * Store de session crypto.
 *
 * Cycle de vie des flags :
 *   isInitializing: true  → spinner affiché par AuthProvider (état initial)
 *   isInitializing: false → AuthProvider a terminé (auth ok ou 401)
 *
 *   isPending: false → accès normal à l'app
 *   isPending: true  → device enregistré mais pas encore approuvé par Device A
 *                       → AuthProvider affiche <PendingApproval> à la place de l'app
 *
 * La KEK ne sort JAMAIS du store : elle vit en mémoire le temps de la session,
 * est purgée au logout, et n'est pas persistée. La clé privée RSA vit dans
 * IndexedDB (cf. crypto.service.ts).
 */
interface CryptoStoreState {
  deviceId: string | null;
  kek: CryptoKey | null;
  isInitializing: boolean;
  isPending: boolean;

  /** Session complète : device vérifié + KEK déchiffrée en mémoire. */
  setSession: (deviceId: string, kek: CryptoKey) => void;
  /** Uniquement le deviceId, sans KEK — utilisé quand le device est en attente. */
  setDeviceId: (deviceId: string) => void;
  setInitializing: (v: boolean) => void;
  setPending: (v: boolean) => void;
  clear: () => void;
}

export const useCryptoStore = create<CryptoStoreState>((set) => ({
  deviceId: null,
  kek: null,
  // Démarre à true : le spinner est visible dès le montage d'AuthProvider.
  isInitializing: true,
  isPending: false,

  setSession: (deviceId, kek) => set({ deviceId, kek, isPending: false }),
  setDeviceId: (deviceId) => set({ deviceId }),
  setInitializing: (v) => set({ isInitializing: v }),
  setPending: (v) => set({ isPending: v }),
  clear: () => set({ deviceId: null, kek: null, isInitializing: false, isPending: false }),
}));
