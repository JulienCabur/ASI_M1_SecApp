/**
 * Service device — enregistrement et récupération des clés de l'appareil
 * courant côté backend (`/fastapi/keys/...`).
 *
 * Le backend ne voit jamais de matière clé en clair : on lui envoie la JWK
 * publique RSA et la KEK déjà wrappée par cette publique (donc opaque pour
 * lui). À la reconnexion, on récupère la KEK chiffrée et on la déballe
 * localement avec la privée non-extractable d'IndexedDB.
 */

import { api } from '@/services/api';

export interface DeviceRegisterResponse {
  device_id: string;
  is_verified: boolean;
}

export const registerDevice = async (
  name: string,
  publicKeyJwk: JsonWebKey,
): Promise<DeviceRegisterResponse> => {
  const { data } = await api.post<DeviceRegisterResponse>('/keys/register_device', {
    name,
    public_key: publicKeyJwk,
  });
  return data;
};

export const storeKek = async (deviceId: string, cipheredKek: string): Promise<void> => {
  // Le backend déclare KeyBase = Form(...), donc on envoie en
  // application/x-www-form-urlencoded plutôt qu'en JSON.
  const form = new URLSearchParams();
  form.append('device_id', deviceId);
  form.append('ciphered_kek', cipheredKek);
  await api.post('/keys/store_kek', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

export interface DeviceKeysResponse {
  public_key: JsonWebKey;
  // null si le device est enregistré mais pas encore vérifié par Device A
  ciphered_kek: string | null;
}

export const getDeviceKeys = async (deviceId: string): Promise<DeviceKeysResponse> => {
  const { data } = await api.get<DeviceKeysResponse>('/keys/get_device_keys', {
    params: { device_id: deviceId },
  });
  return data;
};

export interface DeviceInfo {
  id: string;
  device_name: string;
  is_verified: boolean;
  public_key: JsonWebKey;
}

export const listUnverifiedDevices = async (): Promise<DeviceInfo[]> => {
  const { data } = await api.get<DeviceInfo[]>('/keys/list_unverified_devices');
  return data;
};

export const listVerifiedDevices = async (): Promise<DeviceInfo[]> => {
  const { data } = await api.get<DeviceInfo[]>('/keys/list_verified_devices');
  return data;
};

export const verifyDeviceWithKek = async (deviceId: string, cipheredKek: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('device_id', deviceId);
  form.append('ciphered_kek', cipheredKek);
  await api.post('/keys/verify_device', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

export const rejectDevice = async (deviceId: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('device_id', deviceId);
  await api.post('/keys/reject_device', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};

export const revokeDevice = async (deviceId: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('device_id', deviceId);
  await api.post('/keys/revoke_device', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};
