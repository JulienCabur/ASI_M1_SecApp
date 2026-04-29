import { useState } from 'react';
import { Alert, Button, Form, Input, Modal, Upload, message } from 'antd';
import type { UploadFile } from 'antd';
import { KeyOutlined, UploadOutlined, UserOutlined } from '@ant-design/icons';
import { getCertificateChallenge, resetCredentialsWithCertificate } from '@/services/auth.service';
import { signChallengeWithP12 } from '@/services/certificate.service';

interface CertificateResetValues {
  username: string;
  password: string;
  p12File: { fileList: UploadFile[] };
}

interface CertificateResetModalProps {
  open: boolean;
  onClose: () => void;
}

const CertificateResetModal: React.FC<CertificateResetModalProps> = ({ open, onClose }) => {
  const [form] = Form.useForm<CertificateResetValues>();
  const [submitting, setSubmitting] = useState(false);

  const close = () => {
    form.resetFields();
    onClose();
  };

  const handleSubmit = async (values: CertificateResetValues) => {
    const file = values.p12File?.fileList?.[0]?.originFileObj as File | undefined;
    if (!file) {
      message.error('Sélectionnez votre fichier .p12');
      return;
    }
    setSubmitting(true);
    try {
      const { nonce, timestamp } = await getCertificateChallenge(values.username);
      const { signatureHex, certificatePem } = await signChallengeWithP12(
        file,
        values.password,
        `${nonce}:${timestamp}`,
      );
      await resetCredentialsWithCertificate({
        username: values.username,
        nonce,
        timestamp,
        signature: signatureHex,
        certificate: certificatePem,
      });
      message.success('Demande validée. Vous serez invité à enregistrer une nouvelle clé d\'accès à la prochaine connexion.');
      close();
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'Réinitialisation impossible';
      message.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Réinitialisation par certificat médecin"
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText="Valider"
      cancelText="Annuler"
      confirmLoading={submitting}
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Authentification par certificat"
        description="Utilisez le fichier .p12 reçu lors de votre enregistrement. Sa clé privée signe une preuve d'identité, le mot de passe est défini après reconnexion."
      />
      <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false} preserve={false}>
        <Form.Item
          name="username"
          label="Nom d'utilisateur"
          rules={[{ required: true, message: "Nom d'utilisateur requis" }]}
        >
          <Input prefix={<UserOutlined />} placeholder="dr.dupont" autoComplete="username" />
        </Form.Item>
        <Form.Item
          name="password"
          label="Mot de passe du certificat (.p12)"
          rules={[{ required: true, message: 'Mot de passe requis' }]}
        >
          <Input.Password prefix={<KeyOutlined />} placeholder="•••••••" autoComplete="current-password" />
        </Form.Item>
        <Form.Item
          name="p12File"
          label="Fichier .p12"
          valuePropName="value"
          rules={[{ required: true, message: 'Fichier requis' }]}
        >
          <Upload accept=".p12,.pfx" maxCount={1} beforeUpload={() => false}>
            <Button icon={<UploadOutlined />}>Sélectionner un .p12</Button>
          </Upload>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default CertificateResetModal;
