import Keycloak from 'keycloak-js';
import type { User, Role } from '@/types';

export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL as string,
  realm: import.meta.env.VITE_KEYCLOAK_REALM as string,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID as string,
});

let refreshInterval: ReturnType<typeof setInterval> | null = null;

const LOGIN_REDIRECT = window.location.origin + '/login';
const INIT_TIMEOUT_MS = 10_000;

const logoutToLogin = () =>
  keycloak.logout({ redirectUri: LOGIN_REDIRECT });

const startTokenRefresh = () => {
  stopTokenRefresh();
  refreshInterval = setInterval(() => {
    keycloak.updateToken(60).catch(logoutToLogin);
  }, 50_000);
};

export const initKeycloak = (): Promise<boolean> => {
  keycloak.onTokenExpired = () => {
    keycloak.updateToken(60).catch(logoutToLogin);
  };
  keycloak.onAuthRefreshError = logoutToLogin;

  return new Promise<boolean>((resolve) => {
    let settled = false;

    const timeout = setTimeout(() => {
      if (!settled) {
        settled = true;
        resolve(false);
      }
    }, INIT_TIMEOUT_MS);

    keycloak
      .init({
        onLoad: 'check-sso',
        silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
        pkceMethod: 'S256',
      })
      .then(async (authenticated) => {
        clearTimeout(timeout);
        if (settled) return;
        settled = true;

        if (authenticated) {
          try {
            // Ensure we have a fresh token after a page reload
            await keycloak.updateToken(60);
          } catch {
            resolve(false);
            return;
          }
          startTokenRefresh();
          resolve(true);
        } else {
          resolve(false);
        }
      })
      .catch(() => {
        clearTimeout(timeout);
        if (!settled) {
          settled = true;
          resolve(false);
        }
      });
  });
};

export const stopTokenRefresh = () => {
  if (refreshInterval !== null) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
};

export const getUserFromToken = (): User | null => {
  const parsed = keycloak.tokenParsed;
  if (!parsed) return null;

  const roles: string[] = (parsed as Record<string, { roles?: string[] }>)['realm_access']?.roles ?? [];
  const role = roles.find((r) => r === 'role_patients' || r === 'role_docteurs') as Role | undefined;

  if (!role) return null;

  return {
    id: parsed.sub ?? '',
    firstName: (parsed as Record<string, string>)['given_name'] ?? '',
    lastName: (parsed as Record<string, string>)['family_name'] ?? '',
    email: (parsed as Record<string, string>)['email'] ?? '',
    role,
  };
};

export interface RegistrationParams {
  firstName: string;
  lastName: string;
  email: string;
}

export const getRegistrationUrl = async (_params: RegistrationParams): Promise<string> => {
  // NOTE: Keycloak supports pre-filling first/last name via query params on the register URL.
  // Role assignment must be done post-registration via the Keycloak admin console
  // or via a default role setting in the health_app realm.
  return keycloak.createRegisterUrl({
    redirectUri: window.location.origin + '/auth/callback',
  });
};

export const getResetCredentialsUrl = (): string => {
  const url = import.meta.env.VITE_KEYCLOAK_URL as string;
  const realm = import.meta.env.VITE_KEYCLOAK_REALM as string;
  return `${url}/realms/${realm}/login-actions/reset-credentials`;
};
