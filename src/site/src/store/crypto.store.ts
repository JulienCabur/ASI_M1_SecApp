import { create } from 'zustand';

/**
 * Store de session crypto.
 *
 * On y garde la KEK (CryptoKey AES-GCM non-extractable) et l'identifiant du
 * device courant. La KEK ne sort JAMAIS du store : elle vit en mémoire le temps
 * de la session navigateur, est purgée au logout, et n'est pas persistée.
 * La clé privée RSA, elle, vit dans IndexedDB (cf. crypto.service.ts).
 *
 * Cycle de vie :
 * 1. isInitializing: true au boot (loading des clés)
 * 2. Au succès : setSession() ou setPending() → isInitializing: false
 * 3. Au 401 (auth failure) ou erreur : clear() → isInitializing: false
 * 4. isInitializing doit TOUJOURS devenir false pour déverrouiller l'UI
 */
interface CryptoStoreState {
  deviceId: string | null;
  kek: CryptoKey | null;
  isInitializing: boolean;
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
  isInitializing: true,
  isPending: false,
  isRejected: false,
  pendingSignal: 0,
  setSession: (deviceId, kek) => set({ deviceId, kek, isInitializing: false, isPending: false, isRejected: false }),
  setPending: (deviceId) => set({ deviceId, kek: null, isInitializing: false, isPending: true, isRejected: false }),
  setRejected: () => set({ isRejected: true }),
  incPendingSignal: () => set((s) => ({ pendingSignal: s.pendingSignal + 1 })),
  clear: () => set({ deviceId: null, kek: null, isInitializing: false, isPending: false, isRejected: false, pendingSignal: 0 }),
}));
