import { useEffect } from 'react';
import { App, Spin } from 'antd';
import { fetchMe } from '@/services/auth.service';
import { useAuthStore } from '@/store/auth.store';
import { useCryptoStore } from '@/store/crypto.store';
import { initCryptoSession } from '@/hooks/useCryptoSession';
import { useSecurityMonitor } from '@/hooks/useSecurityMonitor';
import { PendingApproval } from './PendingApproval';
import styles from './AuthProvider.module.scss';

interface AuthProviderProps {
  children: React.ReactNode;
}

/**
 * Bootstrap d'auth en mode BFF : un seul appel `GET /auth/me` au montage
 * de l'app pour savoir si la session cookie est valide.
 *
 * Logique de rendu (ordre strict) :
 *   1. isInitializing === true  → <Spin> (crypto ou auth pas encore terminés)
 *   2. isPending === true        → <PendingApproval> (Device B en attente)
 *   3. sinon                     → children (accès normal à l'app)
 *
 * isInitializing est géré ici dans le .finally() pour être toujours remis
 * à false, même en cas d'erreur inattendue.
 */
export const AuthProvider = ({ children }: AuthProviderProps) => {
  const { setUser, clear: clearAuth } = useAuthStore();
  const { isInitializing, isPending, setInitializing, clear: clearCrypto } = useCryptoStore();

  useSecurityMonitor();

  useEffect(() => {
    let cancelled = false;

    fetchMe()
      .then(async (user) => {
        if (cancelled) return;
        if (!user) {
          clearAuth();
          return;
        }
        setUser(user);
        try {
          await initCryptoSession(user.id);
        } catch (err) {
          // Erreur inattendue dans le bootstrap crypto : on log mais on ne
          // bloque pas l'app. Les pages nécessitant la KEK afficheront un
          // état dégradé.
          console.error('Bootstrap crypto échoué :', err);
        }
      })
      .catch(() => {
        // 401 ou erreur réseau : l'utilisateur n'est pas connecté.
        // On purge les deux stores et on laisse le router afficher /login.
        if (cancelled) return;
        clearAuth();
        clearCrypto();
      })
      .finally(() => {
        // Garantit que le spinner disparaît dans TOUS les cas (auth ok,
        // auth 401, erreur crypto, etc.).
        if (!cancelled) setInitializing(false);
      });

    return () => {
      cancelled = true;
    };
  }, [setUser, clearAuth, clearCrypto, setInitializing]);

  if (isInitializing) {
    return (
      <div className={styles.loader}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <App>
      {isPending ? <PendingApproval /> : children}
    </App>
  );
};
