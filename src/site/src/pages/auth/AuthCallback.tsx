import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { Result, Button, Spin } from 'antd';
import { startLogin } from '@/services/auth.service';

/**
 * En mode BFF, le callback OIDC est traité par le backend (`/fastapi/auth/callback`).
 * Le back redirige ensuite vers la racine (ou `redirect_to`). Cette page sert
 * uniquement de fallback si l'utilisateur arrive ici avec un `?error=...` côté front,
 * ou si une route legacy continue de pointer ici.
 */
const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const error = params.get('error');

  useEffect(() => {
    if (!error) {
      navigate('/', { replace: true });
    }
  }, [error, navigate]);

  if (!error) {
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
          <Button type="primary" key="retry" onClick={() => startLogin('/')}>
            Réessayer
          </Button>,
        ]}
      />
    </div>
  );
};

export default AuthCallback;
