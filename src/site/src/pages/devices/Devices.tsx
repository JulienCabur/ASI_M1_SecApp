import { useEffect, useState } from 'react';
import { App, Button, Empty, Space, Tag, Typography } from 'antd';
import { useCryptoStore } from '@/store/crypto.store';
import { useAuthStore } from '@/store/auth.store';
import {
  importPublicKeyJwk,
  wrapKEKWithRecipientPublicKey,
  wrapPrivateKeyWithRSAKey,
} from '@/services/crypto.service';
import {
  type DeviceInfo,
  listUnverifiedDevices,
  listVerifiedDevices,
  verifyDeviceWithKek,
  rejectDevice,
  revokeDevice,
} from '@/services/device.service';
import style from './devices.module.scss';

const { Title, Text } = Typography;

const Devices: React.FC = () => {
  const { modal, message } = App.useApp();
  // On lit uniquement deviceId depuis le hook React pour le badge "Cet appareil".
  // La KEK est lue via getState() dans les handlers async pour éviter les closures stales.
  const { deviceId } = useCryptoStore();

  const [unverified, setUnverified] = useState<DeviceInfo[]>([]);
  const [verified, setVerified] = useState<DeviceInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [accepting, setAccepting] = useState<string | null>(null);

  const fetchDevices = async () => {
    setLoading(true);
    try {
      const [u, v] = await Promise.all([listUnverifiedDevices(), listVerifiedDevices()]);
      setUnverified(u);
      setVerified(v);
    } catch (err) {
      console.error('[Devices] fetchDevices error:', err);
      void message.error('Impossible de charger les appareils.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchDevices();
  }, []);

  const handleAccept = async (device: DeviceInfo) => {
    // Lire l'état directement depuis les stores (escape hatch Zustand) pour éviter
    // qu'une closure stale après re-render retourne une référence périmée.
    const role = useAuthStore.getState().role;
    const { kek, privateMEK } = useCryptoStore.getState();

    setAccepting(device.id);
    try {
      const recipientPublicKey = await importPublicKeyJwk(device.public_key);
      let cipheredPayload: string;

      if (role === 'role_docteurs') {
        // Médecin : on partage la privée MEK (PKCS8) avec le nouveau device,
        // chiffrée RSA-OAEP par sa pubkey. Le serveur ne voit jamais la privée.
        if (!privateMEK) {
          void message.error('Session cryptographique non disponible. Reconnectez-vous.');
          setAccepting(null);
          return;
        }
        const wrapped = await wrapPrivateKeyWithRSAKey(privateMEK, recipientPublicKey);
        const bytes = new Uint8Array(wrapped);
        let bin = '';
        for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
        cipheredPayload = btoa(bin);
      } else {
        // Patient : on partage la KEK AES-GCM avec le nouveau device.
        if (!kek) {
          void message.error('Session cryptographique non disponible. Reconnectez-vous.');
          setAccepting(null);
          return;
        }
        cipheredPayload = await wrapKEKWithRecipientPublicKey(kek, recipientPublicKey);
      }

      await verifyDeviceWithKek(device.id, cipheredPayload);
      // Libérer le verrou AVANT fetchDevices pour que les autres boutons
      // soient réactivés sans attendre le rechargement de la liste.
      setAccepting(null);
      void message.success(`Appareil "${device.device_name}" approuvé.`);
      await fetchDevices();
    } catch (err) {
      console.error('[Devices] handleAccept failed for device', device.id, ':', err);
      if (err instanceof Error) {
        console.error('[Devices] Error name:', err.name, '— Message:', err.message);
      }
      setAccepting(null);
      void message.error("Erreur lors de l'approbation. Vérifiez la console pour le détail.");
    }
  };

  const handleReject = (device: DeviceInfo) => {
    modal.confirm({
      title: 'Refuser cet appareil ?',
      content: `L'appareil "${device.device_name}" sera supprimé définitivement.`,
      okText: 'Refuser',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await rejectDevice(device.id);
          void message.success('Appareil refusé.');
          await fetchDevices();
        } catch (err) {
          console.error('[Devices] handleReject failed for device', device.id, ':', err);
          void message.error('Erreur lors du refus. Réessayez.');
        }
      },
    });
  };

  const handleRevoke = (device: DeviceInfo) => {
    modal.confirm({
      title: 'Révoquer cet appareil ?',
      content: `L'accès de "${device.device_name}" sera révoqué. Cet appareil ne pourra plus déchiffrer les données.`,
      okText: 'Révoquer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await revokeDevice(device.id);
          void message.success('Appareil révoqué.');
          await fetchDevices();
        } catch (err) {
          console.error('[Devices] handleRevoke failed for device', device.id, ':', err);
          void message.error('Erreur lors de la révocation. Réessayez.');
        }
      },
    });
  };

  return (
    <div className={style.page}>
      <div className={style.header}>
        <Title level={2} style={{ margin: 0 }}>Mes Appareils</Title>
        <Button onClick={() => { void fetchDevices(); }} loading={loading}>
          Rafraîchir
        </Button>
      </div>

      <div className={style.section}>
        <div className={style.sectionTitle}>En attente d'approbation</div>
        {unverified.length === 0 ? (
          <Empty description="Aucun appareil en attente" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          unverified.map((device) => (
            <div key={device.id} className={style.deviceCard}>
              <Text className={style.deviceName}>{device.device_name}</Text>
              <Space className={style.deviceActions}>
                <Button
                  danger
                  size="small"
                  // Désactiver uniquement si une acceptation est en cours
                  // (le refus lui-même ne bloque pas les autres boutons).
                  disabled={accepting !== null}
                  onClick={() => handleReject(device)}
                >
                  Refuser
                </Button>
                <Button
                  type="primary"
                  size="small"
                  loading={accepting === device.id}
                  // Désactiver les AUTRES appareils pendant une opération d'acceptation.
                  disabled={accepting !== null && accepting !== device.id}
                  onClick={() => { void handleAccept(device); }}
                >
                  Accepter
                </Button>
              </Space>
            </div>
          ))
        )}
      </div>

      <div className={style.section}>
        <div className={style.sectionTitle}>Appareils connectés</div>
        {verified.length === 0 ? (
          <Empty description="Aucun appareil connecté" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          verified.map((device) => (
            <div key={device.id} className={style.deviceCard}>
              <Space align="center">
                <Text className={style.deviceName}>{device.device_name}</Text>
                {device.id === deviceId && <Tag color="blue">Cet appareil</Tag>}
              </Space>
              <div className={style.deviceActions}>
                {device.id !== deviceId && (
                  <Button danger size="small" onClick={() => handleRevoke(device)}>
                    Révoquer
                  </Button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Devices;
