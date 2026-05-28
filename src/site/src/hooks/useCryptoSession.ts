/**
 * Bootstrap de la session crypto au login.
 *
 * Quatre trajectoires possibles :
 *
 *  1. Premier login — Device A (premier device de l'utilisateur)
 *     → générer paire RSA + KEK, tout persister, setSession → accès immédiat
 *
 *  2. Premier login — Device B (un autre device existe déjà pour cet utilisateur)
 *     → générer paire RSA, envoyer clé publique, recevoir is_verified: false
 *     → setDeviceId + setPending(true), PAS de KEK → attente d'approbation par Device A
 *
 *  3. Reconnexion — device vérifié (ciphered_kek présent)
 *     → récupérer ciphered_kek, déchiffrer avec clé privée d'IndexedDB, setSession
 *
 *  4. Reconnexion — device toujours en attente (ciphered_kek null)
 *     → setDeviceId + setPending(true) → réaffiche PendingApproval
 *
 * En cas de 404 (device révoqué/rejeté) ou d'incohérence IDB/localStorage :
 *     → purge locale + nouveau bootstrap (retour au cas 1 ou 2)
 *
 * À aucun moment la matière clé symétrique ou la privée RSA ne quittent le
 * navigateur en clair.
 */

import {
  clearPrivateKey,
  clearPublicKey,
  clearWrappedPrivateKey,
  deriveAesKeyFromSecret,
  exportPublicKeyJwk,
  generateKEKFromRSAKey,
  generateExtractableKeyPair,
  hasWrappedPrivateKey,
  loadAndUnwrapDevicePrivateKey,
  savePublicKey,
  unwrapKEKWithRSAKey,
  unwrapPrivateMEKWithDeviceKey,
  wrapAndSaveDevicePrivateKey,
  wrapPrivateKeyWithRSAKey,} from '@/services/crypto.service';
import { deriveDeviceWrapSecret, registerDeviceWrapCredential } from '@/services/webauthn.service';
import { getDeviceKeys, registerDevice, storeKek, storePublicMEK } from '@/services/device.service';
import { logout } from '@/services/auth.service';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import type { Role } from '@/types';

const deviceIdKey      = (userId: string) => `secuapp.device_id.${userId}`;
const deviceNameKey    = (userId: string) => `secuapp.device_name.${userId}`;
const credKey          = (userId: string) => `secuapp.webauthn_cred.${userId}`;
const credTransportsKey = (userId: string) => `secuapp.webauthn_transports.${userId}`;

const loadTransports = (userId: string): AuthenticatorTransport[] => {
  try {
    const raw = localStorage.getItem(credTransportsKey(userId));
    return raw ? (JSON.parse(raw) as AuthenticatorTransport[]) : [];
  } catch {
    return [];
  }
};

/**
 * Déballe la privée device en mémoire, en déclenchant une cérémonie WebAuthn
 * (PRF) si elle n'est pas déjà en cache dans le store.
 *
 * Utilisé à la demande par les composants (PendingApproval, Dossier) pour
 * éviter de multiplier les invites biométriques : une fois déballée, la clé
 * reste en mémoire pour toute la session.
 */
export const getDevicePrivateKey = async (userId: string): Promise<CryptoKey | null> => {
  const cached = useCryptoStore.getState().devicePrivateKey;
  if (cached) return cached;

  const credentialId = localStorage.getItem(credKey(userId));
  if (!credentialId) return null;

  const secret = await deriveDeviceWrapSecret(credentialId, loadTransports(userId));
  const wrapKey = await deriveAesKeyFromSecret(secret);
  const privateKey = await loadAndUnwrapDevicePrivateKey(wrapKey);
  if (privateKey) useCryptoStore.getState().setDevicePrivateKey(privateKey);
  return privateKey;
};

const toBase64 = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
};

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const generateDeviceName = (): string => {
  const ua = navigator.userAgent.replace(/[^\w]/g, '').slice(0, 20);
  const rnd = crypto.randomUUID().slice(0, 8);
  return `secuapp-${ua}-${rnd}`;
};

/**
 * Enregistre un nouveau device.
 *
 * - Si is_verified: true  → Device A : génère et auto-emballe la KEK, charge la session.
 * - Si is_verified: false → Device B : stocke uniquement le deviceId, lève isPending.
 *   La KEK arrivera de Device A via /keys/verify_device.
 */
const bootstrapDevice = async (userId: string, userName: string, role: Role | null): Promise<void> => {
  const store = useCryptoStore.getState();

  // Paire extractable : on doit exporter le PKCS8 pour le chiffrer avant
  // persistance. La privée ne survit en clair qu'en mémoire de session.
  const pair = await generateExtractableKeyPair();

  // Enregistre un passkey plateforme (Windows Hello) dédié au wrapping.
  const { credentialId, secret, transports } = await registerDeviceWrapCredential(userId, userName);
  const prfSecret = secret ?? (await deriveDeviceWrapSecret(credentialId, transports));
  const wrapKey = await deriveAesKeyFromSecret(prfSecret);

  // Persiste la privée device chiffrée (jamais en clair) + la publique (non sensible).
  await wrapAndSaveDevicePrivateKey(pair.privateKey, wrapKey);
  await savePublicKey(pair.publicKey);
  localStorage.setItem(credKey(userId), credentialId);
  localStorage.setItem(credTransportsKey(userId), JSON.stringify(transports));

  // Met en cache un handle non-extractable pour la session.
  const sessionPrivateKey = await loadAndUnwrapDevicePrivateKey(wrapKey);
  if (sessionPrivateKey) store.setDevicePrivateKey(sessionPrivateKey);

  const jwk = await exportPublicKeyJwk(pair.publicKey);
  const name = generateDeviceName();
  const { device_id, is_verified } = await registerDevice(name, jwk);

  // Persister l'identité de cet appareil pour les reconnexions.
  localStorage.setItem(deviceIdKey(userId), device_id);
  localStorage.setItem(deviceNameKey(userId), name);
  store.setDeviceName(name);

  if (!is_verified) {
    // Device B : en attente d'approbation par Device A.
    // On ne génère pas de KEK ici — elle sera poussée par Device A.
    store.setDeviceId(device_id);
    store.setPending(true);
    return;
  }

  if (role === 'role_docteurs') {
    // Médecin Device A : on génère la paire MEK (RSA-OAEP extractable),
    // on wrappe la privée PKCS8 avec la pubkey du device pour persistance
    // côté serveur, et on garde la privée MEK en mémoire pour la session.
    // Pas de KEK AES-GCM perso : un médecin ne chiffre pas ses propres
    // fichiers, il déballe seulement les KEK des patients.
    const doctorPair = await generateExtractableKeyPair();
    const wrappedDoctorPrivateKey = await wrapPrivateKeyWithRSAKey(doctorPair.privateKey, pair.publicKey);
    const doctorPublicKeyJwk = await exportPublicKeyJwk(doctorPair.publicKey);

    await storeKek(device_id, toBase64(wrappedDoctorPrivateKey));
    await storePublicMEK(userId, doctorPublicKeyJwk);

    store.setDoctorSession(device_id, doctorPair.privateKey);
    return;
  }

  // Patient Device A : auto-générer et auto-emballer la KEK AES-GCM.
  const sealed = await generateKEKFromRSAKey(pair.publicKey);
  await storeKek(device_id, toBase64(sealed.wrappedKek));
  store.setSession(device_id, sealed.kek);
};

type RecoveryResult = 'ok' | 'pending' | 'failed' | 'ceremony_failed';

/**
 * Déballe la privée device via WebAuthn, avec UN réessai silencieux si la
 * première cérémonie échoue (annulation accidentelle, timeout, glitch lecteur).
 * Renvoie null si le credential est absent ; relance si les deux essais échouent.
 */
const unlockDevicePrivateKeyWithRetry = async (userId: string): Promise<CryptoKey | null> => {
  try {
    return await getDevicePrivateKey(userId);
  } catch (err) {
    console.warn('[crypto] Cérémonie WebAuthn échouée, nouvel essai…', err);
    return await getDevicePrivateKey(userId);
  }
};

/**
 * Tente de récupérer la session d'un device déjà enregistré.
 *
 * Retourne :
 *   'ok'              → KEK déchiffrée, session chargée
 *   'pending'         → device existe mais pas encore approuvé (ciphered_kek null)
 *   'failed'          → device introuvable (404) ou artefacts absents → re-bootstrap
 *   'ceremony_failed' → cérémonie WebAuthn KO après réessai → logout demandé
 */
const recoverDevice = async (deviceId: string, userId: string, role: Role | null): Promise<RecoveryResult> => {
  // Présence détectée sans cérémonie WebAuthn : blob chiffré + credential.
  if (!(await hasWrappedPrivateKey())) return 'failed';
  if (!localStorage.getItem(credKey(userId))) return 'failed';

  // Restaurer le nom de l'appareil depuis localStorage (persisté au bootstrap).
  const savedName = localStorage.getItem(deviceNameKey(userId));
  if (savedName) useCryptoStore.getState().setDeviceName(savedName);

  let remote;
  try {
    remote = await getDeviceKeys(deviceId);
  } catch {
    // 404 ou erreur réseau : le device n'existe plus côté backend.
    return 'failed';
  }

  if (!remote.ciphered_kek) {
    // Device enregistré mais Device A n'a pas encore approuvé.
    // On NE déclenche PAS de cérémonie WebAuthn ici : la privée device n'est
    // pas encore nécessaire (elle le sera au moment de l'approbation).
    useCryptoStore.getState().setDeviceId(deviceId);
    useCryptoStore.getState().setPending(true);
    return 'pending';
  }

  // Device approuvé : déballer la privée device via WebAuthn (un réessai max).
  let privateKey: CryptoKey | null;
  try {
    privateKey = await unlockDevicePrivateKeyWithRetry(userId);
  } catch {
    return 'ceremony_failed';
  }
  if (!privateKey) return 'failed';

  const wrappedPayload = fromBase64(remote.ciphered_kek);

  if (role === 'role_docteurs') {
    // Pour un médecin, ciphered_kek = privée MEK PKCS8 chiffrée RSA-OAEP
    // par la pubkey de ce device. On la déballe et la garde en mémoire.
    const privateMEK = await unwrapPrivateMEKWithDeviceKey(wrappedPayload, privateKey);
    useCryptoStore.getState().setDoctorSession(deviceId, privateMEK);
  } else {
    // Pour un patient, ciphered_kek = KEK AES-GCM wrappée par la pubkey du device.
    const kek = await unwrapKEKWithRSAKey(wrappedPayload, privateKey);
    useCryptoStore.getState().setSession(deviceId, kek);
  }
  return 'ok';
};

/**
 * Point d'entrée appelé par AuthProvider après un fetchMe() réussi.
 *
 * Ne touche PAS isInitializing — c'est AuthProvider qui le gère dans son
 * .finally() afin de garantir que le spinner disparaît dans tous les cas.
 */
export const initCryptoSession = async (userId: string): Promise<void> => {
  const { role, user } = useAuthStore.getState();
  const userName = user ? (user.email || `${user.firstName} ${user.lastName}`.trim()) : userId;
  const stored = localStorage.getItem(deviceIdKey(userId));

  if (stored) {
    const result = await recoverDevice(stored, userId, role);
    if (result === 'ok' || result === 'pending') {
      // 'pending' : isPending est déjà positionné dans recoverDevice.
      return;
    }

    if (result === 'ceremony_failed') {
      // Cérémonie WebAuthn KO après réessai : on NE re-bootstrappe PAS (cela
      // détruirait le blob chiffré et imposerait une ré-approbation). On
      // déconnecte proprement, l'utilisateur réessaiera au prochain login.
      useCryptoStore.getState().clear();
      useAuthStore.getState().clear();
      await logout();
      window.location.replace('/login');
      return;
    }

    // 'failed' : device disparu côté backend ou IDB corrompue.
    // On purge les artefacts locaux avant de re-bootstrapper.
    localStorage.removeItem(deviceIdKey(userId));
    localStorage.removeItem(deviceNameKey(userId));
    localStorage.removeItem(credKey(userId));
    localStorage.removeItem(credTransportsKey(userId));
    await clearPrivateKey();
    await clearPublicKey();
    await clearWrappedPrivateKey();
  }

  await bootstrapDevice(userId, userName, role);
};
