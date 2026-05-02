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
): Promise<{ deviceId: string; isVerified: boolean }> => {
  const { data } = await api.post<DeviceRegisterResponse>('/keys/register_device', {
    name,
    public_key: publicKeyJwk,
  });
  return { deviceId: data.device_id, isVerified: data.is_verified };
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
  ciphered_kek: string | null;
  is_verified: boolean;
}

export const getDeviceKeys = async (deviceId: string): Promise<DeviceKeysResponse> => {
  const { data } = await api.get<DeviceKeysResponse>('/keys/get_device_keys', {
    params: { device_id: deviceId },
  });
  return data;
};

export interface PendingDevice {
  id: string;
  device_name: string;
  public_key: JsonWebKey;
}

export interface ConnectedDevice {
  id: string;
  device_name: string;
  is_verified: boolean;
}

export const listUnverifiedDevices = async (): Promise<PendingDevice[]> => {
  const { data } = await api.get<PendingDevice[]>('/keys/list_unverified_devices');
  return data;
};

export const listAllDevices = async (): Promise<ConnectedDevice[]> => {
  const { data } = await api.get<ConnectedDevice[]>('/keys/list_devices');
  return data;
};

export const verifyDevice = async (deviceId: string, cipheredKek: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('device_id', deviceId);
  form.append('ciphered_kek', cipheredKek);
  await api.post('/keys/verify_device', form, {
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

export const rejectDevice = async (deviceId: string): Promise<void> => {
  const form = new URLSearchParams();
  form.append('device_id', deviceId);
  await api.post('/keys/reject_device', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
};
