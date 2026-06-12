import { Alert, Button, Input, Modal, Space, Typography, message } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import type { CertificateIssued } from './DoctorRegistrationModal';
import style from './login.module.scss';

const { Text } = Typography;

interface IssuedCertificateModalProps {
  cert: CertificateIssued | null;
  onClose: () => void;
}

const IssuedCertificateModal: React.FC<IssuedCertificateModalProps> = ({ cert, onClose }) => {
  const copyPassword = async () => {
    if (!cert) return;
    try {
      await navigator.clipboard.writeText(cert.password);
      message.success('Mot de passe copié');
    } catch {
      message.error('Copie impossible — sélectionnez le mot de passe à la main');
    }
  };

  return (
    <Modal
      title="Certificat émis"
      open={cert !== null}
      onCancel={onClose}
      maskClosable={false}
      footer={[
        <Button key="ok" type="primary" onClick={onClose}>
          J'ai noté le mot de passe
        </Button>,
      ]}
      destroyOnHidden
    >
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message="Conservez ce mot de passe maintenant"
        description="Il ne sera plus jamais affiché. Sans lui, le fichier .p12 est inutilisable."
      />
      <Text type="secondary">Fichier téléchargé</Text>
      <div className={style.issuedRow}>
        <Text code>{cert?.filename}</Text>
      </div>
      <Text type="secondary">Mot de passe du .p12</Text>
      <Space.Compact style={{ width: '100%' }}>
        <Input.Password value={cert?.password ?? ''} readOnly visibilityToggle />
        <Button icon={<CopyOutlined />} onClick={copyPassword}>
          Copier
        </Button>
      </Space.Compact>
      {cert && (
        <div className={style.issuedHint}>
          <DownloadOutlined /> Téléchargement déclenché automatiquement
        </div>
      )}
    </Modal>
  );
};

export default IssuedCertificateModal;
