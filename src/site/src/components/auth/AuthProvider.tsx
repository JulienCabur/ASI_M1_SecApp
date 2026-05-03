import { useEffect, useState } from 'react';
import { App, Spin } from 'antd';
import { fetchMe } from '@/services/auth.service';
import { useAuthStore } from '@/store/auth.store';
import { useCryptoStore } from '@/store/crypto.store';
import { initCryptoSession } from '@/hooks/useCryptoSession';
import { useDeviceEvents } from '@/hooks/useDeviceEvents';
import PendingApproval from './PendingApproval';
import styles from './AuthProvider.module.scss';

interface AuthProviderProps {
  children: React.ReactNode;
}

/**
 * Bootstrap d'auth en mode BFF : un seul appel `GET /auth/me` au montage
 * de l'app pour savoir si la session cookie est valide. Si oui, on hydrate
 * le store ; sinon, on laisse l'utilisateur sur les routes publiques.
 *
 * Le refresh des tokens est géré côté serveur à la demande (chaque appel à
 * une route protégée fait un refresh si nécessaire), donc plus de setInterval.
 */
export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [initialized, setInitialized] = useState(false);
  const { setUser, clear } = useAuthStore();
  const isPending = useCryptoStore((s) => s.isPending);

  useDeviceEvents();

  useEffect(() => {
    let cancelled = false;
    fetchMe()
      .then(async (user) => {
        if (cancelled) return;
        if (!user) {
          clear();
          return;
        }
        setUser(user);
        try {
          await initCryptoSession(user.id);
        } catch (err) {
          // La crypto n'est pas bloquante pour l'auth : on log et on laisse
          // l'app charger. Les pages qui ont besoin de la KEK afficheront
          // un état dégradé.
          console.error('Bootstrap crypto échoué :', err);
        }
      })
      .catch(() => {
        if (!cancelled) clear();
      })
      .finally(() => {
        if (!cancelled) setInitialized(true);
      });
    return () => {
      cancelled = true;
    };
  }, [setUser, clear]);

  if (!initialized) {
    return (
      <div className={styles.loader}>
        <Spin size="large" />
      </div>
    );
  }

  return <App>{isPending ? <PendingApproval /> : children}</App>;
};
