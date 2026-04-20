import { useEffect, useState } from 'react';
import { App, Spin } from 'antd';
import { keycloak, initKeycloak, getUserFromToken, stopTokenRefresh } from '@/services/auth.service';
import { useAuthStore } from '@/store/auth.store';
import styles from './AuthProvider.module.scss';

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
            logout();
            keycloak.logout({ redirectUri: window.location.origin + '/login' });
          }
        }
        setInitialized(true);
      })
      .catch(() => {
        setInitialized(true);
      });

    return () => {
      stopTokenRefresh();
    };
  }, [setUser, logout]);

  if (!initialized) {
    return (
      <div className={styles.loader}>
        <Spin size="large" />
      </div>
    );
  }

  return <App>{children}</App>;
};
