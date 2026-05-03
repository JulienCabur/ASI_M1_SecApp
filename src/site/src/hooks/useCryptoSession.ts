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
  exportPublicKeyJwk,
  generateKEKFromRSAKey,
  generateKeyPair,
  loadPrivateKey,
  savePrivateKey,
  savePublicKey,
  unwrapKEKWithRSAKey,
} from '@/services/crypto.service';
import { getDeviceKeys, registerDevice, storeKek } from '@/services/device.service';
import { useCryptoStore } from '@/store/crypto.store';

const deviceIdKey = (userId: string) => `secuapp.device_id.${userId}`;

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
const bootstrapDevice = async (userId: string): Promise<void> => {
  const store = useCryptoStore.getState();

  const pair = await generateKeyPair();
  await savePrivateKey(pair.privateKey);
  await savePublicKey(pair.publicKey);

  const jwk = await exportPublicKeyJwk(pair.publicKey);
  const { device_id, is_verified } = await registerDevice(generateDeviceName(), jwk);
  localStorage.setItem(deviceIdKey(userId), device_id);

  if (!is_verified) {
    // Device B : en attente d'approbation par Device A.
    // On ne génère pas de KEK ici — elle sera poussée par Device A.
    store.setDeviceId(device_id);
    store.setPending(true);
    return;
  }

  // Device A (premier device) : auto-générer et auto-emballer la KEK.
  const sealed = await generateKEKFromRSAKey(pair.publicKey);
  await storeKek(device_id, toBase64(sealed.wrappedKek));
  store.setSession(device_id, sealed.kek);
};

type RecoveryResult = 'ok' | 'pending' | 'failed';

/**
 * Tente de récupérer la session d'un device déjà enregistré.
 *
 * Retourne :
 *   'ok'      → KEK déchiffrée, session chargée
 *   'pending' → device existe mais pas encore approuvé (ciphered_kek null)
 *   'failed'  → device introuvable (404) ou clé privée absente → re-bootstrap nécessaire
 */
const recoverDevice = async (deviceId: string): Promise<RecoveryResult> => {
  const privateKey = await loadPrivateKey();
  if (!privateKey) return 'failed';

  let remote;
  try {
    remote = await getDeviceKeys(deviceId);
  } catch {
    // 404 ou erreur réseau : le device n'existe plus côté backend.
    return 'failed';
  }

  if (!remote.ciphered_kek) {
    // Device enregistré mais Device A n'a pas encore approuvé.
    useCryptoStore.getState().setDeviceId(deviceId);
    useCryptoStore.getState().setPending(true);
    return 'pending';
  }

  const wrappedKek = fromBase64(remote.ciphered_kek);
  const kek = await unwrapKEKWithRSAKey(wrappedKek, privateKey);
  useCryptoStore.getState().setSession(deviceId, kek);
  return 'ok';
};

/**
 * Point d'entrée appelé par AuthProvider après un fetchMe() réussi.
 *
 * Ne touche PAS isInitializing — c'est AuthProvider qui le gère dans son
 * .finally() afin de garantir que le spinner disparaît dans tous les cas.
 */
export const initCryptoSession = async (userId: string): Promise<void> => {
  const stored = localStorage.getItem(deviceIdKey(userId));

  if (stored) {
    const result = await recoverDevice(stored);
    if (result === 'ok' || result === 'pending') {
      // 'pending' : isPending est déjà positionné dans recoverDevice.
      return;
    }

    // 'failed' : device disparu côté backend ou IDB corrompue.
    // On purge les artefacts locaux avant de re-bootstrapper.
    localStorage.removeItem(deviceIdKey(userId));
    await clearPrivateKey();
    await clearPublicKey();
  }

  await bootstrapDevice(userId);
};
