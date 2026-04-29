import { useState } from 'react';
import { Navigate } from 'react-router';
import { Typography } from 'antd';
import { useAuth } from '@/hooks/useAuth';
import LoginActions from '@/components/login/LoginActions';
import RoleSelection, { type RoleChoice } from '@/components/login/RoleSelection';
import style from './login.module.scss';

const { Title, Text } = Typography;

const Login: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const [choice, setChoice] = useState<RoleChoice | null>(null);

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
    </div>
  );
};

export default Login;
