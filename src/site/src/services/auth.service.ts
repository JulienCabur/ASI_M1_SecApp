/**
 * Service d'authentification — pattern BFF.
 *
 * Le frontend ne parle JAMAIS à Keycloak directement. Toutes les opérations
 * passent par le backend FastAPI qui orchestre le flow OIDC et stocke les
 * tokens dans un cookie httpOnly côté navigateur. Côté JS, on ne voit donc
 * jamais d'access/refresh token.
 */

import type { Role, User } from '@/types';
import { apiFetch, ApiError } from '@/services/api';

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/fastapi';

interface MeResponse {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  roles: string[];
}

const toUser = (me: MeResponse): User | null => {
  const role = me.roles.find((r) => r === 'role_patients' || r === 'role_docteurs') as Role | undefined;
  if (!role) return null;
  return {
    id: me.id,
    firstName: me.first_name,
    lastName: me.last_name,
    email: me.email,
    role,
  };
};

/** Lance le flow OIDC : redirige le navigateur vers /auth/login (back),
 *  qui à son tour redirige vers la page de login Keycloak. */
export const startLogin = (redirectTo: string = '/'): void => {
  const target = encodeURIComponent(redirectTo);
  window.location.href = `${API_BASE}/auth/login?redirect_to=${target}`;
};

/** Récupère le profil utilisateur depuis le cookie session.
 *  Renvoie `null` si pas de session valide. */
export const fetchMe = async (): Promise<User | null> => {
  try {
    const me = await apiFetch<MeResponse>('/auth/me');
    return toUser(me);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
};

/** Demande au back de rafraîchir le token côté serveur (rotation cookie). */
export const refreshSession = async (): Promise<boolean> => {
  try {
    await apiFetch('/auth/refresh', { method: 'POST' });
    return true;
  } catch {
    return false;
  }
};

interface LogoutResponse {
  status: string;
  logout_url: string;
}

/** Logout en trois temps :
 *   1. POST /auth/logout : le back révoque le refresh_token et efface ses cookies.
 *   2. Cleanup local : store Zustand + cookies JS-accessibles sur ce domaine.
 *   3. Redirect vers `logout_url` Keycloak : seule façon d'effacer les cookies
 *      SSO posés par Keycloak sur `localhost:8443` (différent du domaine du front).
 *      Keycloak nous renverra ensuite sur `/login` via `post_logout_redirect_uri`. */
export const logout = async (): Promise<void> => {
  let logoutUrl = '/login';
  try {
    const data = await apiFetch<LogoutResponse>('/auth/logout', { method: 'POST' });
    if (data?.logout_url) logoutUrl = data.logout_url;
  } catch {
    // Le back peut être indisponible ; on continue le cleanup local quand même.
  }
  clearClientCookies();
  try {
    const { useAuthStore } = await import('@/store/auth.store');
    useAuthStore.getState().clear();
  } catch {
    // ignore
  }
  window.location.replace(logoutUrl);
};

/** Supprime tous les cookies lisibles par le JS sur le domaine courant.
 *  Les cookies httpOnly (session, oidc_state) ne sont pas accessibles ici —
 *  c'est le back qui s'en charge via Set-Cookie de suppression. */
const clearClientCookies = (): void => {
  const cookies = document.cookie ? document.cookie.split(';') : [];
  for (const raw of cookies) {
    const eq = raw.indexOf('=');
    const name = (eq > -1 ? raw.substring(0, eq) : raw).trim();
    if (!name) continue;
    document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Strict`;
    document.cookie = `${name}=; Max-Age=0; path=/`;
  }
};

/** Demande de réinitialisation des identifiants (passwordless) par mail.
 *  Le lien envoyé par Keycloak permet de ré-enrôler une passkey WebAuthn.
 *  Réponse uniforme côté serveur (anti-énumération). */
export const requestCredentialsReset = async (email: string): Promise<void> => {
  await apiFetch('/auth/reset/request', {
    method: 'POST',
    body: { email },
  });
};

/** Reset par certificat médecin : challenge -> signature locale -> POST.
 *  La signature elle-même est exécutée par le composant qui détient le `.p12`. */
export interface CertificateChallenge {
  nonce: string;
  timestamp: string;
}

export const getCertificateChallenge = async (username: string): Promise<CertificateChallenge> => {
  const params = new URLSearchParams({ username });
  return apiFetch<CertificateChallenge>(`/auth/challenge?${params.toString()}`);
};

export interface CertificateResetPayload {
  username: string;
  nonce: string;
  timestamp: string;
  signature: string;
  certificate: string;
}

export const resetCredentialsWithCertificate = async (payload: CertificateResetPayload): Promise<void> => {
  await apiFetch('/auth/reset/with-certificate', {
    method: 'POST',
    body: payload,
  });
};
