import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import { Alert, Button, Card, Typography } from 'antd';
import {
  ArrowLeftOutlined,
  MailOutlined,
  MobileOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { startLogin } from '@/services/auth.service';
import AddDeviceModal from './AddDeviceModal';
import EmailResetModal from './EmailResetModal';
import CertificateResetModal from './CertificateResetModal';
import CertificateLoginModal from './CertificateLoginModal';
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
  const [searchParams] = useSearchParams();
  const urlError = searchParams.get('error');
  const flowType = searchParams.get('flow_type');

  const [emailResetOpen, setEmailResetOpen] = useState(false);
  const [addDeviceOpen, setAddDeviceOpen] = useState(false);
  const [certResetOpen, setCertResetOpen] = useState(false);
  const [certLoginOpen, setCertLoginOpen] = useState(false);
  const [registerOpen, setRegisterOpen] = useState(false);
  const [issuedCert, setIssuedCert] = useState<CertificateIssued | null>(null);

  // `role` est le choix UI ('patient' | 'doctor'), pas le rôle JWT Keycloak
  // ('role_patients' / 'role_docteurs').
  useEffect(() => {
    if (flowType !== 'add_device') return;
    if (role === 'patient') startLogin('/', 'add_device');
    else if (role === 'doctor') setCertLoginOpen(true);
  }, [role, flowType]);

  // Patient : flow OIDC standard (passkey/TOTP côté Keycloak).
  // Médecin : on exige une preuve de possession du cert AVANT Keycloak ;
  // le bouton ouvre le modal cert qui redirigera ensuite sur authorize_url.
  const handleLogin = () => {
    if (role === 'doctor') {
      setCertLoginOpen(true);
    } else {
      startLogin('/');
    }
  };

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
        {urlError === 'auth_failed' && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
            message="Passkey introuvable sur cet appareil"
            description={
              role === 'doctor'
                ? "Votre passkey Windows Hello n'est pas enregistré sur cet appareil. Étape 1 : enregistrez cet appareil (email). Étape 2 : reconnectez-vous avec votre certificat."
                : "Votre clé d'accès n'est pas enregistrée sur cet appareil ou ce navigateur."
            }
            action={
              <Button
                size="small"
                icon={<MobileOutlined />}
                onClick={() => setAddDeviceOpen(true)}
              >
                Enregistrer cet appareil
              </Button>
            }
          />
        )}
        <div className={style.actions}>
          <Button
            type="primary"
            size="large"
            block
            icon={role === 'doctor' ? <SafetyCertificateOutlined /> : undefined}
            onClick={handleLogin}
          >
            {role === 'doctor' ? 'Se connecter avec mon certificat' : 'Se connecter'}
          </Button>
          {role === 'patient' ? (
            <>
              <Button size="large" block icon={<MobileOutlined />} onClick={() => setAddDeviceOpen(true)}>
                Premier accès sur cet appareil
              </Button>
              <Button size="large" block icon={<MailOutlined />} onClick={() => setEmailResetOpen(true)}>
                Réinitialiser ma clé d'accès
              </Button>
            </>
          ) : (
            <>
              <Button size="large" block icon={<MobileOutlined />} onClick={() => setAddDeviceOpen(true)}>
                Premier accès sur cet appareil
              </Button>
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

      <AddDeviceModal open={addDeviceOpen} onClose={() => setAddDeviceOpen(false)} />
      <EmailResetModal open={emailResetOpen} onClose={() => setEmailResetOpen(false)} />
      <CertificateResetModal open={certResetOpen} onClose={() => setCertResetOpen(false)} />
      <CertificateLoginModal
        open={certLoginOpen}
        onClose={() => setCertLoginOpen(false)}
        redirectTo="/"
        flowType={flowType ?? 'standard'}
      />
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
