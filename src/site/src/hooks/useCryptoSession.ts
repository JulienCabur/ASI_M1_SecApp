/**
 * Bootstrap de la session crypto au login.
 *
 * Trois trajectoires :
 *  1. Premier login (jamais d'appareil enregistré pour cet utilisateur sur ce
 *     navigateur) → on génère une paire RSA, on la persiste (privée non-
 *     extractable) en IndexedDB, on enregistre l'appareil côté backend, on
 *     produit une KEK scellée par RSA-OAEP et on la stocke.
 *  2. Reconnexion (privée présente en IDB et device_id en localStorage) → on
 *     récupère la KEK chiffrée du back, on la déballe localement avec la
 *     privée, et on la met en mémoire (store crypto).
 *  3. Incohérence (l'un des deux manque) → on repasse par le chemin (1).
 *
 * À aucun moment la matière clé symétrique ou la privée RSA ne quittent le
 * navigateur en clair. Ni les logs, ni le serveur, ni un admin du back ne
 * voient quoi que ce soit d'exploitable.
 */

import {
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
  return `device-${ua}-${rnd}`;
};

const bootstrapDevice = async (userId: string): Promise<void> => {
  const pair = await generateKeyPair();
  await savePrivateKey(pair.privateKey);
  await savePublicKey(pair.publicKey);

  const jwk = await exportPublicKeyJwk(pair.publicKey);
  const { deviceId, isVerified } = await registerDevice(generateDeviceName(), jwk);
  localStorage.setItem(deviceIdKey(userId), deviceId);

  if (isVerified) {
    // Premier appareil : on génère la KEK et on démarre la session
    const sealed = await generateKEKFromRSAKey(pair.publicKey);
    await storeKek(deviceId, toBase64(sealed.wrappedKek));
    useCryptoStore.getState().setSession(deviceId, sealed.kek);
  } else {
    // Appareil secondaire : on attend que DA approuve et fournisse la KEK partagée
    useCryptoStore.getState().setPending(deviceId);
  }
};

const recoverDevice = async (deviceId: string): Promise<boolean> => {
  useCryptoStore.getState().setPending(deviceId);

  const privateKey = await loadPrivateKey();
  if (!privateKey) return false;

  const remote = await getDeviceKeys(deviceId);

  if (!remote.is_verified || !remote.ciphered_kek) {
    useCryptoStore.getState().setPending(deviceId);
    return true;
  }

  const wrappedKek = fromBase64(remote.ciphered_kek);
  const kek = await unwrapKEKWithRSAKey(wrappedKek, privateKey);
  useCryptoStore.getState().setSession(deviceId, kek);
  return true;
};

export const initCryptoSession = async (userId: string): Promise<void> => {
  const stored = localStorage.getItem(deviceIdKey(userId));
  if (stored) {
    try {
      const ok = await recoverDevice(stored);
      if (ok) return;
    } catch {
      // récupération impossible → on repart sur un device frais
    }
    localStorage.removeItem(deviceIdKey(userId));
  }
  await bootstrapDevice(userId);
};
