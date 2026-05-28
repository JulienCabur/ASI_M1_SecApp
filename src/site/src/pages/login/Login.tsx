import { useState } from 'react';
import { Navigate, useSearchParams } from 'react-router';
import { Button, Typography } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';
import LoginActions from '@/components/login/LoginActions';
import RoleSelection, { type RoleChoice } from '@/components/login/RoleSelection';
import CAInfoModal from '@/components/login/CAInfoModal';
import style from './login.module.scss';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const error = searchParams.get('error');

  // Pré-sélectionner le rôle patient sur un échec Keycloak (la plupart des utilisateurs
  // sont patients). Sur flow_type=add_device, on ne force pas : un médecin peut aussi
  // revenir ici après avoir enregistré son passkey.
  const initialChoice: RoleChoice | null = error === 'auth_failed' ? 'patient' : null;

  const [choice, setChoice] = useState<RoleChoice | null>(initialChoice);
  const [caInfoOpen, setCaInfoOpen] = useState(false);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className={style.container}>
      {choice === null ? (
        <>
          <div className={style.header}>
            <Title level={2} className={style.title}>Bienvenue</Title>
            <Text className={style.subtitle}>Choisissez votre profil pour continuer</Text>
          </div>
          <RoleSelection onSelect={setChoice} />
        </>
      ) : (
        <LoginActions role={choice} onBack={() => setChoice(null)} />
      )}
      <Button
        type="link"
        size="small"
        icon={<SafetyCertificateOutlined />}
        className={style.caBtn}
        onClick={() => setCaInfoOpen(true)}
      >
        Informations sur le certificat CA
      </Button>
      <CAInfoModal open={caInfoOpen} onClose={() => setCaInfoOpen(false)} />
    </div>
  );
};

export default Login;
