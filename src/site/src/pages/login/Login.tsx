import { useState } from 'react';
import { Navigate } from 'react-router';
import { Alert, Button, Card, Form, Input, Modal, Typography, Upload, message } from 'antd';
import type { UploadFile } from 'antd';
import {
  ArrowLeftOutlined,
  KeyOutlined,
  MailOutlined,
  MedicineBoxOutlined,
  SafetyCertificateOutlined,
  UploadOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';
import {
  getCertificateChallenge,
  requestCredentialsReset,
  resetCredentialsWithCertificate,
  startLogin,
} from '@/services/auth.service';
import { signChallengeWithP12 } from '@/services/certificate.service';
import style from './login.module.scss';

const { Title, Text } = Typography;

type RoleChoice = 'patient' | 'doctor';

interface CertificateFormValues {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

interface EmailResetValues {
  email: string;
}

interface CertificateResetValues {
  username: string;
  password: string;
  p12File: { fileList: UploadFile[] };
}

const EmailResetModal = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  const [form] = Form.useForm<EmailResetValues>();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const close = () => {
    form.resetFields();
    setSubmitted(false);
    onClose();
  };

  const handleSubmit = async ({ email }: EmailResetValues) => {
    setSubmitting(true);
    try {
      await requestCredentialsReset(email);
      setSubmitted(true);
    } catch {
      // Le back répond toujours 200 par sécurité (anti-énumération) ;
      // un échec ici signifie un vrai souci réseau.
      message.error('Impossible de contacter le serveur. Réessayez dans un instant.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Réinitialiser ma clé d'accès"
      open={open}
      onCancel={close}
      footer={
        submitted
          ? [<Button key="ok" type="primary" onClick={close}>Fermer</Button>]
          : [
              <Button key="cancel" onClick={close}>Annuler</Button>,
              <Button key="ok" type="primary" loading={submitting} onClick={() => form.submit()}>
                Envoyer le lien
              </Button>,
            ]
      }
      destroyOnHidden
    >
      {submitted ? (
        <Alert
          type="success"
          showIcon
          message="Si un compte correspond à cette adresse, un lien d'enregistrement vient d'y être envoyé."
          description="Le lien est valable 1 heure. Vous pourrez ré-enrôler votre passkey ou clé de sécurité depuis ce lien."
        />
      ) : (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Authentification sans mot de passe"
            description="Cette application utilise une clé d'accès (passkey / WebAuthn). Si vous l'avez perdue, on vous envoie un lien pour en enregistrer une nouvelle."
          />
          <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false} preserve={false}>
            <Form.Item
              name="email"
              label="Adresse e-mail"
              rules={[
                { required: true, message: 'E-mail requis' },
              ]}
            >
              <Input prefix={<MailOutlined />} placeholder="vous@example.com" autoFocus />
            </Form.Item>
          </Form>
        </>
      )}
    </Modal>
  );
};

const CertificateResetModal = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
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

const Login: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [choice, setChoice] = useState<RoleChoice | null>(null);
  const [certModalOpen, setCertModalOpen] = useState(false);
  const [emailResetOpen, setEmailResetOpen] = useState(false);
  const [certResetOpen, setCertResetOpen] = useState(false);
  const [certForm] = Form.useForm<CertificateFormValues>();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleLogin = () => startLogin('/');

  const handleCertSubmit = (_values: CertificateFormValues) => {
    // TODO: brancher /auth/register_doctor (existait déjà côté back).
    setCertModalOpen(false);
    certForm.resetFields();
  };

  if (choice === null) {
    return (
      <div className={style.container}>
        <div className={style.header}>
          <Title level={2} className={style.title}>Bienvenue</Title>
          <Text className={style.subtitle}>Choisissez votre profil pour continuer</Text>
        </div>
        <div className={style.tiles}>
          <Card hoverable className={style.tile} onClick={() => setChoice('patient')}>
            <UserOutlined className={style.icon} />
            <Title level={3} style={{ margin: 0 }}>Patient</Title>
            <Text type="secondary">Accéder à mon dossier médical</Text>
          </Card>
          <Card hoverable className={style.tile} onClick={() => setChoice('doctor')}>
            <MedicineBoxOutlined className={style.icon} />
            <Title level={3} style={{ margin: 0 }}>Médecin</Title>
            <Text type="secondary">Accéder à mes patients</Text>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className={style.container}>
      <Card className={style.card}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => setChoice(null)}
          className={style.back}
        >
          Retour
        </Button>
        <div className={style.header}>
          <Title level={2} style={{ margin: 0 }}>
            {choice === 'patient' ? 'Espace patient' : 'Espace médecin'}
          </Title>
          <Text type="secondary">Connectez-vous pour continuer</Text>
        </div>
        <div className={style.actions}>
          <Button type="primary" size="large" block onClick={handleLogin}>
            Se connecter
          </Button>
          {choice === 'patient' ? (
            <Button size="large" block icon={<MailOutlined />} onClick={() => setEmailResetOpen(true)}>
              Réinitialiser ma clé d'accès
            </Button>
          ) : (
            <Button
              size="large"
              block
              icon={<SafetyCertificateOutlined />}
              onClick={() => setCertResetOpen(true)}
            >
              Réinitialiser via certificat
            </Button>
          )}
          {choice === 'doctor' && (
            <Button
              size="large"
              block
              icon={<SafetyCertificateOutlined />}
              onClick={() => setCertModalOpen(true)}
            >
              Création de certificat
            </Button>
          )}
        </div>
      </Card>

      <EmailResetModal open={emailResetOpen} onClose={() => setEmailResetOpen(false)} />
      <CertificateResetModal open={certResetOpen} onClose={() => setCertResetOpen(false)} />

      <Modal
        title="Création de certificat"
        open={certModalOpen}
        onCancel={() => setCertModalOpen(false)}
        onOk={() => certForm.submit()}
        okText="Créer"
        cancelText="Annuler"
        destroyOnHidden
      >
        <Form
          form={certForm}
          layout="vertical"
          onFinish={handleCertSubmit}
          requiredMark={false}
          preserve={false}
        >
          <Form.Item
            name="username"
            label="Nom d'utilisateur"
            rules={[{ required: true, message: "Nom d'utilisateur requis" }]}
          >
            <Input placeholder="jdupont" />
          </Form.Item>
          <Form.Item
            name="email"
            label="Adresse e-mail"
            rules={[
              { required: true, message: 'E-mail requis' },
              { type: 'email', message: 'Adresse e-mail invalide' },
            ]}
          >
            <Input placeholder="jean.dupont@example.com" />
          </Form.Item>
          <Form.Item
            name="first_name"
            label="Prénom"
            rules={[{ required: true, message: 'Prénom requis' }]}
          >
            <Input placeholder="Jean" />
          </Form.Item>
          <Form.Item
            name="last_name"
            label="Nom"
            rules={[{ required: true, message: 'Nom requis' }]}
          >
            <Input placeholder="Dupont" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Login;
