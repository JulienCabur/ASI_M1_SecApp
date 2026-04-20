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
    console.log('AuthProvider initializing...');
    
    initKeycloak()
      .then((authenticated) => {
        console.log('Keycloak initialized, authenticated:', authenticated);
        
        if (authenticated) {
          const user = getUserFromToken();
          console.log('User from token:', user);
          console.log('JWT Token:', keycloak.token);
          
          if (user) {
            setUser(user, keycloak.token ?? '');
          } else {
            console.warn('Token present but no user found');
            logout();
            keycloak.logout();
          }
        } else {
          console.log('User not authenticated');
        }
        setInitialized(true);
      })
      .catch((error) => {
        console.error('Keycloak init error:', error);
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
