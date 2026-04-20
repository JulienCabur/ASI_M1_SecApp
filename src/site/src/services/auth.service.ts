import Keycloak from 'keycloak-js';
import type { User, Role } from '@/types';

export const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL as string,
  realm: import.meta.env.VITE_KEYCLOAK_REALM as string,
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID as string,
});

let refreshInterval: ReturnType<typeof setInterval> | null = null;

export const initKeycloak = (): Promise<boolean> => {
  return keycloak
    .init({
      onLoad: 'check-sso',
      silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
      pkceMethod: 'S256',
    })
    .then((authenticated) => {
      if (authenticated) {
        // Refresh token every 50s before the 5-min expiry
        refreshInterval = setInterval(() => {
          keycloak.updateToken(60).catch(() => {
            keycloak.logout();
          });
        }, 50_000);
      }
      return authenticated;
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
