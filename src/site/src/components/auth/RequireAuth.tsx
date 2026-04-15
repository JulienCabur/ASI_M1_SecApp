import { Outlet } from 'react-router';
import { useAuth } from '@/hooks/useAuth';
import { keycloak } from '@/services/auth.service';

export const RequireAuth = () => {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    // Delegate login entirely to Keycloak — no internal /login page
    keycloak.login({ redirectUri: window.location.origin + '/auth/callback' });
    return null;
  }

  return <Outlet />;
};
