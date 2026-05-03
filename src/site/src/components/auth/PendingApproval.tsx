import { useState } from 'react';
import { Alert, Button, Result, Typography } from 'antd';
import { MobileOutlined } from '@ant-design/icons';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import { getDeviceKeys } from '@/services/device.service';
import { loadPrivateKey, unwrapKEKWithRSAKey } from '@/services/crypto.service';
import { logout } from '@/services/auth.service';
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
 *
 *  A — Approuvé  : ciphered_kek présent → déchiffrer KEK → lever isPending → accès app
 *  B — Refusé    : HTTP 404 (device supprimé par Device A) → purge complète → logout
 *  C — En attente: ciphered_kek null → afficher message d'attente, pas d'action
 */
export const PendingApproval = () => {
  const { deviceId, setSession, setPending, clear: clearCrypto } = useCryptoStore();
  const { clear: clearAuth } = useAuthStore();

  const [checking, setChecking] = useState(false);
  const [stillPending, setStillPending] = useState(false);

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
          // IDB corrompue : impossible de déchiffrer → forcer un nouveau bootstrap.
          // On traite ça comme un refus pour simplifier le parcours utilisateur.
          throw Object.assign(new Error('private key missing'), { isRejection: true });
        }
        const wrappedKek = fromBase64(remote.ciphered_kek);
        const kek = await unwrapKEKWithRSAKey(wrappedKek, privateKey);
        setSession(deviceId, kek);
        setPending(false);
        // AuthProvider re-rend automatiquement children grâce à isPending: false.
        return;
      }

      // Scénario C — Toujours en attente (ciphered_kek null).
      setStillPending(true);

    } catch (err: unknown) {
      // Scénario B — HTTP 404 : Device A a refusé la demande, le device a été supprimé.
      // On purge tout et on redirige vers /login.
      const isAxios404 =
        typeof err === 'object' &&
        err !== null &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 404;

      const isRejection =
        typeof err === 'object' &&
        err !== null &&
        'isRejection' in err;

      if (isAxios404 || isRejection) {
        clearCrypto();
        clearAuth();
        await logout();
        // logout() gère la redirection vers /login.
        return;
      }

      // Erreur réseau ou autre : ne pas déconnecter, laisser l'utilisateur réessayer.
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
            <Text>
              Cet appareil a été enregistré mais n'est pas encore approuvé.
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
