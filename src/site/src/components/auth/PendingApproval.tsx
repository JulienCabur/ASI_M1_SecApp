import { useEffect } from 'react';
import { Button, Card, Result, Spin, Typography } from 'antd';
import { MobileOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { getDeviceKeys } from '@/services/device.service';
import { unwrapKEKWithRSAKey } from '@/services/crypto.service';
import { loadPrivateKey, clearPrivateKey, clearPublicKey } from '@/services/crypto.service';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import { ApiError } from '@/services/api';

const { Title, Text } = Typography;

const deviceIdKey = (userId: string) => `secuapp.device_id.${userId}`;

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const PendingApproval: React.FC = () => {
  const deviceId = useCryptoStore((s) => s.deviceId);
  const isRejected = useCryptoStore((s) => s.isRejected);
  const userId = useAuthStore((s) => s.user?.id ?? '');

  // Vérification unique au montage — filet de sécurité si le SSE a manqué
  // l'événement pendant une coupure réseau avant la reconnexion.
  useEffect(() => {
    if (!deviceId) return;
    let cancelled = false;

    const check = async () => {
      try {
        const remote = await getDeviceKeys(deviceId);
        if (!cancelled && remote.is_verified && remote.ciphered_kek) {
          const privateKey = await loadPrivateKey();
          if (!privateKey) {
            useCryptoStore.getState().setPending(deviceId);
            return;
          }
          const kek = await unwrapKEKWithRSAKey(fromBase64(remote.ciphered_kek), privateKey);
          useCryptoStore.getState().setSession(deviceId, kek);
          return;
        }
        if (!cancelled) {
          useCryptoStore.getState().setPending(deviceId);
        }
      } catch (e) {
        if (!cancelled && e instanceof ApiError && (e.status === 404 || e.status === 400)) {
          useCryptoStore.getState().setRejected();
          return;
        }
        if (!cancelled) {
          useCryptoStore.getState().setPending(deviceId);
        }
      }
    };

    void check();
    return () => { cancelled = true; };
  }, [deviceId]);

  const handleRetry = async () => {
    await clearPrivateKey();
    await clearPublicKey();
    localStorage.removeItem(deviceIdKey(userId));
    window.location.reload();
  };

  if (isRejected) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: '#f5f5f5' }}>
        <Card style={{ maxWidth: 480, width: '100%', textAlign: 'center' }}>
          <Result
            icon={<CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
            title="Connexion refusée"
            subTitle="L'appareil de confiance a refusé cette connexion. Vous pouvez réessayer ou contacter l'administrateur."
            extra={
              <Button type="primary" onClick={() => void handleRetry()}>
                Réessayer
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', background: 'linear-gradient(135deg, #1E3A60 0%, #2D5A8C 100%)' }}>
      <Card style={{ maxWidth: 480, width: '100%', textAlign: 'center', borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
        <MobileOutlined style={{ fontSize: 56, color: '#2D5A8C', marginBottom: 16, display: 'block' }} />
        <Title level={3} style={{ margin: 0 }}>Nouvel appareil détecté</Title>
        <Text type="secondary" style={{ display: 'block', marginTop: 8, marginBottom: 24 }}>
          Vous vous connectez depuis un nouvel appareil. Un appareil déjà connecté doit approuver cette connexion pour continuer.
        </Text>
        <Spin size="large" />
        <Text type="secondary" style={{ display: 'block', marginTop: 16, fontSize: 13 }}>
          En attente d'approbation…
        </Text>
        <Button
          type="text"
          danger
          style={{ marginTop: 24 }}
          onClick={() => void handleRetry()}
        >
          Annuler
        </Button>
      </Card>
    </div>
  );
};

export default PendingApproval;
