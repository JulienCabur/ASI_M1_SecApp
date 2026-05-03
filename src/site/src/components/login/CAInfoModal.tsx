import { useEffect, useState } from 'react';
import { Alert, Button, Input, Modal, Space, Spin, Typography, message } from 'antd';
import { CopyOutlined, DownloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { api } from '@/services/api';

const { Text } = Typography;

interface CAInfoModalProps {
  open: boolean;
  onClose: () => void;
}

const CAInfoModal: React.FC<CAInfoModalProps> = ({ open, onClose }) => {
  const [hash, setHash] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setHasError(false);
    api
      .get<{ hash: string }>('/check-authenticity/hash_ca')
      .then((r) => setHash(r.data.hash))
      .catch(() => setHasError(true))
      .finally(() => setLoading(false));
  }, [open]);

  const copyHash = async () => {
    if (!hash) return;
    try {
      await navigator.clipboard.writeText(hash);
      message.success('Empreinte copiée');
    } catch {
      message.error('Copie impossible');
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const response = await api.get('/check-authenticity/download_ca', { responseType: 'blob' });
      const url = URL.createObjectURL(response.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'ca-chain.crt';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      message.error('Téléchargement impossible');
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Modal
      title={
        <>
          <SafetyCertificateOutlined style={{ marginRight: 8 }} />
          Certificat de l'autorité de confiance
        </>
      }
      open={open}
      onCancel={onClose}
      footer={[
        <Button
          key="download"
          type="primary"
          icon={<DownloadOutlined />}
          loading={downloading}
          onClick={handleDownload}
        >
          Télécharger le certificat
        </Button>,
        <Button key="close" onClick={onClose}>
          Fermer
        </Button>,
      ]}
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Installer le certificat de confiance"
        description={
          <>
            Pour accéder au site sans avertissement de sécurité :
            <ol style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
              <li>Téléchargez le certificat ci-dessous</li>
              <li>Importez-le dans les autorités de certification de confiance de votre navigateur</li>
              <li>Redémarrez votre navigateur</li>
            </ol>
          </>
        }
      />
      <Text type="secondary">Empreinte SHA-1 du certificat</Text>
      {loading && <Spin size="small" style={{ display: 'block', marginTop: 8 }} />}
      {hasError && (
        <Text type="danger" style={{ display: 'block', marginTop: 8 }}>
          Impossible de récupérer l'empreinte
        </Text>
      )}
      {hash && (
        <Space.Compact style={{ width: '100%', marginTop: 8 }}>
          <Input
            value={hash}
            readOnly
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
          <Button icon={<CopyOutlined />} onClick={copyHash}>
            Copier
          </Button>
        </Space.Compact>
      )}
    </Modal>
  );
};

export default CAInfoModal;
