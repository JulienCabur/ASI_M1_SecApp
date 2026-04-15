import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Spin, Result, Button } from 'antd';
import { useAuth } from '@/hooks/useAuth';
import { keycloak } from '@/services/auth.service';

const AuthCallback: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Keycloak JS adapter processes the URL callback automatically during initKeycloak()
    // which runs inside AuthProvider before this component mounts.
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  if (isAuthenticated) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" tip="Redirection..." />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <Result
        status="error"
        title="Authentification échouée"
        subTitle="Impossible de terminer la connexion. Veuillez réessayer."
        extra={[
          <Button
            type="primary"
            key="retry"
            onClick={() => keycloak.login({ redirectUri: window.location.origin + '/auth/callback' })}
          >
            Réessayer
          </Button>,
        ]}
      />
    </div>
  );
};

export default AuthCallback;
