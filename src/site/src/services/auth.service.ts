/**
 * Service d'authentification — pattern BFF.
 *
 * Le frontend ne parle JAMAIS à Keycloak directement. Toutes les opérations
 * passent par le backend FastAPI qui orchestre le flow OIDC et stocke les
 * tokens dans un cookie httpOnly côté navigateur. Côté JS, on ne voit donc
 * jamais d'access/refresh token.
 */

import type { Role, User } from '@/types';
import { api, API_BASE, ApiError } from '@/services/api';

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
 *  qui à son tour redirige vers la page de login Keycloak.
 *  `flowType` peut valoir "add_device" pour le flux d'ajout d'appareil :
 *  le callback sautera alors cleanup_stale_credentials(). */
export const startLogin = (redirectTo: string = '/', flowType: string = 'standard'): void => {
  const target = encodeURIComponent(redirectTo);
  const ftParam = flowType !== 'standard' ? `&flow_type=${encodeURIComponent(flowType)}` : '';
  window.location.href = `${API_BASE}/auth/login?redirect_to=${target}${ftParam}`;
};

/** Récupère le profil utilisateur depuis le cookie session.
 *  Renvoie `null` si pas de session valide. */
export const fetchMe = async (): Promise<User | null> => {
  try {
    const { data } = await api.get<MeResponse>('/auth/me');
    return toUser(data);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return null;
    throw err;
  }
};

/** Demande au back de rafraîchir le token côté serveur (rotation cookie). */
export const refreshSession = async (): Promise<boolean> => {
  try {
    await api.post('/auth/refresh');
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
    const { data } = await api.post<LogoutResponse>('/auth/logout');
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
  await api.post('/auth/reset/request', { email });
};

/** Demande d'ajout d'un nouvel appareil par mail.
 *  Comme requestCredentialsReset mais le callback OIDC ne supprimera pas
 *  les passkeys existants (les autres appareils gardent leur accès).
 *  Réponse uniforme côté serveur (anti-énumération). */
export const requestAddDevice = async (email: string): Promise<void> => {
  await api.post('/auth/add_device/request', { email });
};

/** Reset par certificat médecin : challenge -> signature locale -> POST.
 *  La signature elle-même est exécutée par le composant qui détient le `.p12`. */
export interface CertificateChallenge {
  nonce: string;
  timestamp: string;
}

export const getCertificateChallenge = async (username: string): Promise<CertificateChallenge> => {
  const { data } = await api.get<CertificateChallenge>('/auth/cert/login/challenge', {
    params: { username },
  });
  return data;
};

export interface CertificateResetPayload {
  username: string;
  nonce: string;
  timestamp: string;
  signature: string;
  certificate: string;
}

export const resetCredentialsWithCertificate = async (payload: CertificateResetPayload): Promise<void> => {
  await api.post('/auth/reset/with-certificate', payload);
};

/** Login médecin par certificat (gate avant Keycloak).
 *  Le challenge `/cert/login/...` est distinct de `/auth/challenge` côté back :
 *  on évite ainsi qu'une preuve produite pour un reset puisse être rejouée
 *  pour ouvrir une session, et inversement. */
export const getCertificateLoginChallenge = async (username: string): Promise<CertificateChallenge> => {
  const { data } = await api.get<CertificateChallenge>('/auth/cert/login/challenge', {
    params: { username },
  });
  return data;
};

export interface CertificateLoginPayload extends CertificateResetPayload {
  redirect_to: string;
}

interface CertificateLoginResponse {
  authorize_url: string;
}

/** Soumet la preuve cert au BFF. Au succès, le BFF a posé `secuapp_oidc_state`
 *  (httpOnly) avec le `cert_proven_username` ; il nous reste à naviguer le
 *  navigateur vers `authorize_url` pour terminer le flow OIDC normal. */
export const submitCertificateLoginProof = async (
  payload: CertificateLoginPayload,
): Promise<string> => {
  const { data } = await api.post<CertificateLoginResponse>('/auth/cert/login/proof', payload);
  return data.authorize_url;
};

/** Enregistrement d'un nouveau médecin : génère côté back un CSR signé par la PKI,
 *  crée le compte Keycloak et renvoie le .p12 (base64) + son mot de passe.
 *  Le back attend du multipart/form-data (FastAPI `Form(...)`), pas du JSON. */
export interface RegisterDoctorInput {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  organization: string;
}

export interface RegisterDoctorResult {
  status: string;
  username: string;
  certificate_b64: string;
  password: string;
  filename: string;
}

export const registerDoctor = async (input: RegisterDoctorInput): Promise<RegisterDoctorResult> => {
  const form = new FormData();
  form.append('username', input.username);
  form.append('email', input.email);
  form.append('first_name', input.first_name);
  form.append('last_name', input.last_name);
  form.append('date_of_birth', input.date_of_birth);
  form.append('organization', input.organization);
  const { data } = await api.post<RegisterDoctorResult>('/auth/register_doctor', form);
  return data;
};
