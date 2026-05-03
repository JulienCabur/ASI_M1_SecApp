import { create } from 'zustand';

/**
 * Store de session crypto.
 *
 * On y garde la KEK (CryptoKey AES-GCM non-extractable) et l'identifiant du
 * device courant. La KEK ne sort JAMAIS du store : elle vit en mémoire le temps
 * de la session navigateur, est purgée au logout, et n'est pas persistée.
 * La clé privée RSA, elle, vit dans IndexedDB (cf. crypto.service.ts).
 */
interface CryptoStoreState {
  deviceId: string | null;
  kek: CryptoKey | null;
  isPending: boolean;
  isRejected: boolean;
  pendingSignal: number;
  setSession: (deviceId: string, kek: CryptoKey) => void;
  setPending: (deviceId: string) => void;
  setRejected: () => void;
  incPendingSignal: () => void;
  clear: () => void;
}

export const useCryptoStore = create<CryptoStoreState>((set) => ({
  deviceId: null,
  kek: null,
  isPending: true,
  isRejected: false,
  pendingSignal: 0,
  setSession: (deviceId, kek) => set({ deviceId, kek, isPending: false, isRejected: false }),
  setPending: (deviceId) => set({ deviceId, kek: null, isPending: true, isRejected: false }),
  setRejected: () => set({ isRejected: true }),
  incPendingSignal: () => set((s) => ({ pendingSignal: s.pendingSignal + 1 })),
  clear: () => set({ deviceId: null, kek: null, isPending: false, isRejected: false, pendingSignal: 0 }),
}));
