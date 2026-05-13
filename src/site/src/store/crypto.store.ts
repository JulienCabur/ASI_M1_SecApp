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
 *
 * Pour les médecins, on n'utilise pas `kek` mais `privateMEK` : une privée
 * RSA-OAEP partagée entre tous les devices du médecin, qui sert à déballer
 * les KEK des patients (wrappées avec la public MEK correspondante). Elle
 * est gardée en mémoire seulement (jamais persistée localement).
 */
interface CryptoStoreState {
  deviceId: string | null;
  deviceName: string | null;
  kek: CryptoKey | null;
  /** Privée MEK du médecin (RSA-OAEP, extractable, en mémoire seulement). */
  privateMEK: CryptoKey | null;
  isInitializing: boolean;
  isPending: boolean;

  /** Session patient : device vérifié + KEK AES-GCM déchiffrée en mémoire. */
  setSession: (deviceId: string, kek: CryptoKey) => void;
  /** Session médecin : device vérifié + privée MEK RSA déballée en mémoire. */
  setDoctorSession: (deviceId: string, privateMEK: CryptoKey) => void;
  /** Uniquement le deviceId, sans KEK — utilisé quand le device est en attente. */
  setDeviceId: (deviceId: string) => void;
  /** Nom lisible de cet appareil, généré à l'enregistrement et affiché dans PendingApproval. */
  setDeviceName: (name: string) => void;
  setInitializing: (v: boolean) => void;
  setPending: (v: boolean) => void;
  clear: () => void;
}

export const useCryptoStore = create<CryptoStoreState>((set) => ({
  deviceId: null,
  deviceName: null,
  kek: null,
  privateMEK: null,
  // Démarre à true : le spinner est visible dès le montage d'AuthProvider.
  isInitializing: true,
  isPending: false,

  setSession: (deviceId, kek) => set({ deviceId, kek, privateMEK: null, isPending: false }),
  setDoctorSession: (deviceId, privateMEK) => set({ deviceId, privateMEK, kek: null, isPending: false }),
  setDeviceId: (deviceId) => set({ deviceId }),
  setDeviceName: (name) => set({ deviceName: name }),
  setInitializing: (v) => set({ isInitializing: v }),
  setPending: (v) => set({ isPending: v }),
  clear: () => set({
    deviceId: null,
    deviceName: null,
    kek: null,
    privateMEK: null,
    isInitializing: false,
    isPending: false,
  }),
}));
