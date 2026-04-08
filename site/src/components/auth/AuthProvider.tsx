import { useEffect, useState } from 'react';
import { App, Spin } from 'antd';
import { keycloak, initKeycloak, getUserFromToken, stopTokenRefresh } from '@/services/auth.service';
import { useAuthStore } from '@/store/auth.store';

interface AuthProviderProps {
  children: React.ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [initialized, setInitialized] = useState(false);
  const { setUser, logout } = useAuthStore();

  useEffect(() => {
    initKeycloak()
      .then((authenticated) => {
        if (authenticated) {
          const user = getUserFromToken();
          if (user) {
            setUser(user, keycloak.token ?? '');
          } else {
            // Token present but role not recognized — force logout
            logout();
            keycloak.logout();
          }
        }
        setInitialized(true);
      })
      .catch(() => {
        // Keycloak unreachable (dev without infra) — allow public pages to load
        setInitialized(true);
      });

    return () => {
      stopTokenRefresh();
    };
  }, [setUser, logout]);

  if (!initialized) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  return <App>{children}</App>;
};
