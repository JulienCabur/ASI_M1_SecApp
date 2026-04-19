import { useState } from 'react';
import { Navigate } from 'react-router';
import { Button, Card, Form, Input, Modal, Typography } from 'antd';
import { UserOutlined, MedicineBoxOutlined, ArrowLeftOutlined, SafetyCertificateOutlined } from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';
import { keycloak, getResetCredentialsUrl } from '@/services/auth.service';
import style from './login.module.scss';

const { Title, Text } = Typography;

type RoleChoice = 'patient' | 'doctor';

interface CertificateFormValues {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
}

const Login: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [choice, setChoice] = useState<RoleChoice | null>(null);
  const [certModalOpen, setCertModalOpen] = useState(false);
  const [certForm] = Form.useForm<CertificateFormValues>();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  const handleLogin = () => {
    keycloak.login({ redirectUri: window.location.origin + '/auth/callback' });
  };

  const handleReset = () => {
    window.location.href = getResetCredentialsUrl();
  };

  const handleCertSubmit = (_values: CertificateFormValues) => {
    // TODO: branch on backend endpoint for certificate creation
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
          <Button
            size="large"
            block
            onClick={handleReset}
            disabled={choice === 'doctor'}
          >
            Réinitialiser mes identifiants
          </Button>
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
