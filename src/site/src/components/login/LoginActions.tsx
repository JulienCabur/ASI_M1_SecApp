import { useState } from 'react';
import { Button, Card, Typography } from 'antd';
import {
  ArrowLeftOutlined,
  MailOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { startLogin } from '@/services/auth.service';
import EmailResetModal from './EmailResetModal';
import CertificateResetModal from './CertificateResetModal';
import DoctorRegistrationModal, { type CertificateIssued } from './DoctorRegistrationModal';
import IssuedCertificateModal from './IssuedCertificateModal';
import type { RoleChoice } from './RoleSelection';
import style from './login.module.scss';

const { Title, Text } = Typography;

interface LoginActionsProps {
  role: RoleChoice;
  onBack: () => void;
}

const LoginActions: React.FC<LoginActionsProps> = ({ role, onBack }) => {
  const [emailResetOpen, setEmailResetOpen] = useState(false);
  const [certResetOpen, setCertResetOpen] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [issuedCert, setIssuedCert] = useState<CertificateIssued | null>(null);

  const handleLogin = () => startLogin('/');

  return (
    <>
      <Card className={style.card}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={onBack}
          className={style.back}
        >
          Retour
        </Button>
        <div className={style.header}>
          <Title level={2} style={{ margin: 0 }}>
            {role === 'patient' ? 'Espace patient' : 'Espace médecin'}
          </Title>
          <Text type="secondary">Connectez-vous pour continuer</Text>
        </div>
        <div className={style.actions}>
          <Button type="primary" size="large" block onClick={handleLogin}>
            Se connecter
          </Button>
          {role === 'patient' ? (
            <Button size="large" block icon={<MailOutlined />} onClick={() => setEmailResetOpen(true)}>
              Réinitialiser ma clé d'accès
            </Button>
          ) : (
            <>
              <Button
                size="large"
                block
                icon={<SafetyCertificateOutlined />}
                onClick={() => setCertResetOpen(true)}
              >
                Réinitialiser via certificat
              </Button>
              <Button
                size="large"
                block
                icon={<SafetyCertificateOutlined />}
                onClick={() => setRegisterOpen(true)}
              >
                Création de certificat
              </Button>
            </>
          )}
        </div>
      </Card>

      <EmailResetModal open={emailResetOpen} onClose={() => setEmailResetOpen(false)} />
      <CertificateResetModal open={certResetOpen} onClose={() => setCertResetOpen(false)} />
      <DoctorRegistrationModal
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        onIssued={setIssuedCert}
      />
      <IssuedCertificateModal cert={issuedCert} onClose={() => setIssuedCert(null)} />
    </>
  );
};

export default LoginActions;
