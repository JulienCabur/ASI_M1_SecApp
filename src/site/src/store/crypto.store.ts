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
  setSession: (deviceId: string, kek: CryptoKey) => void;
  clear: () => void;
}

export const useCryptoStore = create<CryptoStoreState>((set) => ({
  deviceId: null,
  kek: null,
  setSession: (deviceId, kek) => set({ deviceId, kek }),
  clear: () => set({ deviceId: null, kek: null }),
}));
