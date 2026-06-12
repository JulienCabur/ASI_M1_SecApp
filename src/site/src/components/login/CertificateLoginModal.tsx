import { useState } from 'react';
import { Alert, Button, Form, Input, Modal, Upload, message } from 'antd';
import type { UploadFile } from 'antd';
import { KeyOutlined, UploadOutlined, UserOutlined } from '@ant-design/icons';
import {
  getCertificateLoginChallenge,
  submitCertificateLoginProof,
} from '@/services/auth.service';
import { signChallengeWithP12 } from '@/services/certificate.service';

interface CertificateLoginValues {
  username: string;
  password: string;
  p12File: { fileList: UploadFile[] };
}

interface CertificateLoginModalProps {
  open: boolean;
  onClose: () => void;
  redirectTo?: string;
  flowType?: string;
}

/**
 * Login médecin par certificat (gate avant la redirection Keycloak).
 *
 * Flow :
 *   1. Challenge récupéré côté back (`nonce`, `timestamp`).
 *   2. Signature locale via `signChallengeWithP12` (RSA-PSS / SHA-256, MAX salt).
 *   3. POST de la preuve : le back vérifie + lie `cert_proven_username` au state OIDC.
 *   4. Au succès, `window.location` saute vers Keycloak avec `authorize_url`.
 *
 * Le `.p12` ne quitte JAMAIS le navigateur (la clé privée est utilisée localement
 * pour signer ; seule la signature et le cert public sont envoyés au back).
 */
const CertificateLoginModal: React.FC<CertificateLoginModalProps> = ({
  open,
  onClose,
  redirectTo = '/',
  flowType = 'standard',
}) => {
  const [form] = Form.useForm<CertificateLoginValues>();
  const [submitting, setSubmitting] = useState(false);

  const close = () => {
    form.resetFields();
    onClose();
  };

  const handleSubmit = async (values: CertificateLoginValues) => {
    const file = values.p12File?.fileList?.[0]?.originFileObj as File | undefined;
    if (!file) {
      message.error('Sélectionnez votre fichier .p12');
      return;
    }
    setSubmitting(true);
    try {
      const { nonce, timestamp } = await getCertificateLoginChallenge(values.username);
      const { signatureHex, certificatePem } = await signChallengeWithP12(
        file,
        values.password,
        `${nonce}:${timestamp}`,
      );
      const authorizeUrl = await submitCertificateLoginProof({
        username: values.username,
        nonce,
        timestamp,
        signature: signatureHex,
        certificate: certificatePem,
        redirect_to: redirectTo,
        flow_type: flowType,
      });
      // Top-level navigation : le cookie `secuapp_oidc_state` (Strict, httpOnly)
      // posé par le back voyage avec cette navigation puisqu'on est same-site.
      window.location.href = authorizeUrl;
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'Authentification par certificat impossible';
      message.error(detail);
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Connexion par certificat médecin"
      open={open}
      onCancel={close}
      onOk={() => form.submit()}
      okText="Se connecter"
      cancelText="Annuler"
      confirmLoading={submitting}
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Preuve de possession requise"
        description="Votre certificat .p12 signe localement un défi à usage unique. Le fichier ne quitte pas votre navigateur ; vous serez ensuite redirigé vers Keycloak pour finaliser la connexion."
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

export default CertificateLoginModal;
