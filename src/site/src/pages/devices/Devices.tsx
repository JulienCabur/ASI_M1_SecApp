import { useEffect, useState } from 'react';
import { Button, Card, Col, Empty, Row, Spin, Tag, Typography, message } from 'antd';
import { MobileOutlined, ReloadOutlined } from '@ant-design/icons';
import {
  listUnverifiedDevices,
  listAllDevices,
  verifyDevice,
  rejectDevice,
  revokeDevice,
  type PendingDevice,
  type ConnectedDevice,
} from '@/services/device.service';
import { useCryptoStore } from '@/store/crypto.store';
import style from './devices.module.scss';

const { Title, Text } = Typography;

const toBase64 = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
};

const Devices: React.FC = () => {
  const [pending, setPending] = useState<PendingDevice[]>([]);
  const [connected, setConnected] = useState<ConnectedDevice[]>([]);
  const [loadingPending, setLoadingPending] = useState(false);
  const [loadingConnected, setLoadingConnected] = useState(false);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const currentDeviceId = useCryptoStore((s) => s.deviceId);

  const fetchPending = async () => {
    setLoadingPending(true);
    try {
      setPending(await listUnverifiedDevices());
    } catch {
      message.error('Impossible de charger les appareils en attente');
    } finally {
      setLoadingPending(false);
    }
  };

  const fetchConnected = async () => {
    setLoadingConnected(true);
    try {
      const all = await listAllDevices();
      setConnected(all.filter((d) => d.is_verified));
    } catch {
      message.error('Impossible de charger les appareils connectés');
    } finally {
      setLoadingConnected(false);
    }
  };

  const pendingSignal = useCryptoStore((s) => s.pendingSignal);

  // fetchConnected une seule fois au montage
  useEffect(() => {
    void fetchConnected();
  }, []);

  // fetchPending au montage (signal=0) puis à chaque événement SSE device_pending
  useEffect(() => {
    void fetchPending();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingSignal]);

  const handleAccept = async (device: PendingDevice) => {
    const kek = useCryptoStore.getState().kek;
    if (!kek) {
      message.error('Session cryptographique non initialisée');
      return;
    }

    setAcceptingId(device.id);
    try {
      const pubB = await crypto.subtle.importKey(
        'jwk',
        device.public_key,
        { name: 'RSA-OAEP', hash: 'SHA-512' },
        false,
        ['wrapKey'],
      );

      const wrapped = await crypto.subtle.wrapKey('raw', kek, pubB, { name: 'RSA-OAEP' });
      const cipheredKek = toBase64(wrapped);

      await verifyDevice(device.id, cipheredKek);
      message.success(`Appareil "${device.device_name}" approuvé`);
      setPending((prev) => prev.filter((d) => d.id !== device.id));
      void fetchConnected();
    } catch {
      message.error(`Échec de l'approbation de "${device.device_name}"`);
    } finally {
      setAcceptingId(null);
    }
  };

  const handleReject = async (device: PendingDevice) => {
    setRejectingId(device.id);
    try {
      await rejectDevice(device.id);
      message.success(`Appareil "${device.device_name}" refusé`);
      setPending((prev) => prev.filter((d) => d.id !== device.id));
    } catch {
      message.error(`Échec du refus de "${device.device_name}"`);
    } finally {
      setRejectingId(null);
    }
  };

  const handleRevoke = async (device: ConnectedDevice) => {
    setRevokingId(device.id);
    try {
      await revokeDevice(device.id);
      message.success(`Appareil "${device.device_name}" révoqué`);
      setConnected((prev) => prev.filter((d) => d.id !== device.id));
    } catch {
      message.error(`Échec de la révocation de "${device.device_name}"`);
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <div className={style.devices}>
      <Title level={3}>Gestion des connexions</Title>

      <div className={style.section}>
        <div className={style.sectionTitle}>
          <Title level={5} style={{ display: 'inline', marginRight: 12 }}>
            En attente d'approbation
          </Title>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={fetchPending}
            loading={loadingPending}
          >
            Rafraîchir
          </Button>
        </div>

        {loadingPending ? (
          <Spin />
        ) : pending.length === 0 ? (
          <Empty description="Aucun appareil en attente" />
        ) : (
          <Row gutter={[16, 16]}>
            {pending.map((device) => (
              <Col key={device.id} xs={24} sm={12} md={8}>
                <Card
                  size="small"
                  title={
                    <>
                      <MobileOutlined style={{ marginRight: 8, color: '#2D5A8C' }} />
                      {device.device_name}
                    </>
                  }
                  extra={
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Button
                        type="primary"
                        size="small"
                        loading={acceptingId === device.id}
                        disabled={rejectingId === device.id}
                        onClick={() => void handleAccept(device)}
                      >
                        Accepter
                      </Button>
                      <Button
                        danger
                        size="small"
                        loading={rejectingId === device.id}
                        disabled={acceptingId === device.id}
                        onClick={() => void handleReject(device)}
                      >
                        Refuser
                      </Button>
                    </div>
                  }
                >
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    En attente de votre approbation
                  </Text>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </div>

      <div className={style.section}>
        <div className={style.sectionTitle}>
          <Title level={5}>Appareils connectés</Title>
        </div>

        {loadingConnected ? (
          <Spin />
        ) : connected.length === 0 ? (
          <Empty description="Aucun autre appareil connecté" />
        ) : (
          <Row gutter={[16, 16]}>
            {connected.map((device) => (
              <Col key={device.id} xs={24} sm={12} md={8}>
                <Card
                  size="small"
                  title={
                    <>
                      <MobileOutlined style={{ marginRight: 8, color: '#2D5A8C' }} />
                      {device.device_name}
                      {device.id === currentDeviceId && (
                        <Tag color="blue" style={{ marginLeft: 8, fontSize: 11 }}>
                          Cet appareil
                        </Tag>
                      )}
                    </>
                  }
                  extra={
                    device.id === currentDeviceId ? null : (
                      <Button
                        danger
                        size="small"
                        loading={revokingId === device.id}
                        onClick={() => void handleRevoke(device)}
                      >
                        Révoquer
                      </Button>
                    )
                  }
                >
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {device.id === currentDeviceId ? 'Session active' : 'Appareil approuvé'}
                  </Text>
                </Card>
              </Col>
            ))}
          </Row>
        )}
      </div>
    </div>
  );
};

export default Devices;
