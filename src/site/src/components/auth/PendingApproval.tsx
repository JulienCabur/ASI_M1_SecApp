import { useState } from 'react';
import { Alert, Button, Result, Typography } from 'antd';
import { MobileOutlined } from '@ant-design/icons';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import { getDeviceKeys } from '@/services/device.service';
import {
  clearPrivateKey,
  clearPublicKey,
  loadPrivateKey,
  unwrapKEKWithRSAKey,
  unwrapPrivateMEKWithDeviceKey,
} from '@/services/crypto.service';
import { logout } from '@/services/auth.service';
import { ApiError } from '@/services/api';
import styles from './PendingApproval.module.scss';

const { Text } = Typography;

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

/**
 * Écran de blocage pour un Device B non encore approuvé.
 *
 * Trois scénarios au clic sur "Vérifier mon statut" :
 *  A — Approuvé  : ciphered_kek présent → déchiffrer KEK → lever isPending → accès app
 *  B — Refusé    : HTTP 404 ou 401 → purge + logout → /login
 *  C — En attente: ciphered_kek null → afficher message d'attente
 *
 * Porte de sortie manuelle : "Se déconnecter" → purge + logout → /login immédiat.
 */
export const PendingApproval = () => {
  const { deviceId, deviceName, setSession, setDoctorSession, setPending, clear: clearCrypto } = useCryptoStore();
  const { role, clear: clearAuth } = useAuthStore();

  const [checking, setChecking] = useState(false);
  const [stillPending, setStillPending] = useState(false);

  const handleCancel = async () => {
    await clearPrivateKey();
    await clearPublicKey();
    localStorage.clear();
    clearCrypto();
    clearAuth();
    await logout();
    window.location.replace('/login');
  };

  const handleCheck = async () => {
    if (!deviceId) return;

    setChecking(true);
    setStillPending(false);

    try {
      const remote = await getDeviceKeys(deviceId);

      // Scénario A — Device A a approuvé : ciphered_kek est disponible.
      if (remote.ciphered_kek) {
        const privateKey = await loadPrivateKey();
        if (!privateKey) {
          throw new ApiError('Clé privée introuvable en IndexedDB', 404, null);
        }
        const wrapped = fromBase64(remote.ciphered_kek);

        if (role === 'role_docteurs') {
          // Médecin : Device A a wrappé la privée MEK PKCS8 pour ce device.
          const privateMEK = await unwrapPrivateMEKWithDeviceKey(wrapped, privateKey);
          setDoctorSession(deviceId, privateMEK);
        } else {
          // Patient : Device A a wrappé la KEK AES-GCM pour ce device.
          const kek = await unwrapKEKWithRSAKey(wrapped, privateKey);
          setSession(deviceId, kek);
        }
        setPending(false);
        return;
      }

      // Scénario C — Toujours en attente (ciphered_kek null ou undefined).
      setStillPending(true);

    } catch (err: unknown) {
      // Scénario B — device supprimé (404) ou session expirée (401).
      if (err instanceof ApiError && (err.status === 404 || err.status === 401)) {
        await handleCancel();
        return;
      }
      console.error('[PendingApproval] handleCheck error:', err);
      setStillPending(true);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className={styles.container}>
      <Result
        icon={<MobileOutlined className={styles.icon} />}
        title="Appareil en attente d'approbation"
        subTitle={
          <div className={styles.subtitle}>
            {deviceName && (
              <Text strong style={{ display: 'block', marginBottom: 8 }}>
                Cet appareil : <code>{deviceName}</code>
              </Text>
            )}
            <Text>
              Connectez-vous sur votre appareil principal, accédez à{' '}
              <strong>Mes Appareils</strong> et cliquez sur{' '}
              <strong>Accepter</strong> pour cet appareil.
            </Text>
          </div>
        }
        extra={[
          <Button
            key="check"
            type="primary"
            size="large"
            loading={checking}
            onClick={() => { void handleCheck(); }}
          >
            Vérifier mon statut
          </Button>,
          <Button
            key="cancel"
            size="large"
            danger
            onClick={() => { void handleCancel(); }}
          >
            Se déconnecter
          </Button>,
        ]}
      />

      {stillPending && (
        <div className={styles.alert}>
          <Alert
            type="info"
            showIcon
            message="Pas encore approuvé"
            description="Votre appareil principal n'a pas encore validé cette demande. Réessayez dans quelques instants."
          />
        </div>
      )}
    </div>
  );
};
