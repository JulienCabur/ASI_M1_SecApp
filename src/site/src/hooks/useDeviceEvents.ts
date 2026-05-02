/**
 * Hook SSE — remplace tout le polling périodique lié aux devices.
 *
 * Ouvre une connexion Server-Sent Events sur /fastapi/events/stream
 * et réagit aux 4 événements émis par le backend :
 *   - device_pending  → incrémente pendingSignal (Navbar + Devices se rafraîchissent)
 *   - device_approved → déchiffre la KEK reçue et démarre la session (DB)
 *   - device_rejected → passe isRejected à true (DB)
 *   - device_revoked  → expulse le device courant et recharge la page
 *
 * Le hook se (re)connecte automatiquement via EventSource et vérifie le statut
 * du device au moment de chaque (re)connexion pour rattraper les événements
 * manqués pendant une coupure réseau.
 */

import { useEffect } from 'react';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import { loadPrivateKey, unwrapKEKWithRSAKey } from '@/services/crypto.service';
import { getDeviceKeys } from '@/services/device.service';
import { ApiError } from '@/services/api';

const SSE_URL = '/fastapi/events/stream';

type DeviceApprovedEvent = {
  device_id: string;
  is_verified?: boolean;
  ciphered_kek?: string | null;
};

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const recoverApproval = async (deviceId: string, cipheredKek: string): Promise<void> => {
  try {
    const priv = await loadPrivateKey();
    if (!priv) {
      useCryptoStore.getState().setPending(deviceId);
      return;
    }
    const kek = await unwrapKEKWithRSAKey(fromBase64(cipheredKek), priv);
    useCryptoStore.getState().setSession(deviceId, kek);
  } catch {
    useCryptoStore.getState().setPending(deviceId);
  }
};

const checkPendingStatus = async (deviceId: string): Promise<void> => {
  try {
    const remote = await getDeviceKeys(deviceId);
    if (remote.is_verified && remote.ciphered_kek) {
      await recoverApproval(deviceId, remote.ciphered_kek);
      return;
    }
    useCryptoStore.getState().setPending(deviceId);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 400)) {
      useCryptoStore.getState().setRejected();
      return;
    }
    useCryptoStore.getState().setPending(deviceId);
  }
};

export const useDeviceEvents = (): void => {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) return;

    const es = new EventSource(SSE_URL, { withCredentials: true });

    es.onopen = () => {
      useCryptoStore.getState().incPendingSignal();
      const { deviceId } = useCryptoStore.getState();
      if (deviceId) {
        void checkPendingStatus(deviceId);
      }
    };

    es.addEventListener('device_pending', () => {
      useCryptoStore.getState().incPendingSignal();
    });

    es.addEventListener('device_approved', (e: MessageEvent) => {
      const data = JSON.parse(e.data) as DeviceApprovedEvent;
      const { deviceId } = useCryptoStore.getState();
      if (data.device_id !== deviceId) return;
      if (!data.is_verified || !data.ciphered_kek) {
        useCryptoStore.getState().setPending(data.device_id);
        return;
      }
      void recoverApproval(data.device_id, data.ciphered_kek);
    });

    es.addEventListener('device_rejected', (e: MessageEvent) => {
      const data = JSON.parse(e.data) as { device_id: string };
      if (data.device_id === useCryptoStore.getState().deviceId) {
        useCryptoStore.getState().setRejected();
      }
    });

    es.addEventListener('device_revoked', (e: MessageEvent) => {
      const data = JSON.parse(e.data) as { device_id: string };
      if (data.device_id === useCryptoStore.getState().deviceId) {
        useCryptoStore.getState().clear();
        useAuthStore.getState().clear();
        window.location.reload();
      }
    });

    return () => es.close();
  }, [isAuthenticated]);
};
