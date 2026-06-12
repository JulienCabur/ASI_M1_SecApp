/**
 * WebAuthnService — protège la clé privée de device au repos via un passkey.
 *
 * On utilise l'extension PRF (Pseudo-Random Function, basée sur hmac-secret
 * côté CTAP2.1). Le passkey produit un secret de 32 octets *déterministe* pour
 * un sel donné : la même cérémonie (même authenticator + même sel) redonne
 * toujours le même secret, mais ce secret n'existe NULLE PART tant que
 * l'utilisateur n'a pas validé la cérémonie (présence + vérification user :
 * biométrie / PIN / clé physique).
 *
 * Ce secret sert ensuite (via HKDF, cf. crypto.service) à dériver une clé
 * AES-GCM qui chiffre la clé privée RSA du device dans IndexedDB. Conséquence :
 * un attaquant qui exfiltre IndexedDB (XSS persistante, vol de profil disque)
 * récupère un blob chiffré inexploitable sans l'authenticator physique.
 *
 * Tout est purement client-side : aucun enregistrement/attestation côté
 * serveur. Le credential ne sert pas à *authentifier* mais à *dériver une clé*.
 */

/** Sel PRF fixe : doit rester stable pour que le secret dérivé soit reproductible. */
const PRF_SALT = new TextEncoder().encode('secuapp:device-key-wrap:v1');

const toBase64Url = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
};

const fromBase64Url = (b64url: string): ArrayBuffer => {
  const b64 = b64url.replace(/-/g, '+').replace(/_/g, '/');
  const pad = b64.length % 4 === 0 ? '' : '='.repeat(4 - (b64.length % 4));
  const bin = atob(b64 + pad);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const toArrayBuffer = (src: BufferSource): ArrayBuffer => {
  const bytes = src instanceof ArrayBuffer ? new Uint8Array(src) : new Uint8Array(src.buffer, src.byteOffset, src.byteLength);
  const out = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(out).set(bytes);
  return out;
};

/** WebAuthn + extension PRF disponibles dans ce contexte (HTTPS / localhost requis). */
export const isWebAuthnPrfSupported = (): boolean =>
  typeof window !== 'undefined' &&
  typeof window.PublicKeyCredential !== 'undefined' &&
  typeof navigator.credentials?.create === 'function' &&
  typeof navigator.credentials?.get === 'function';

/** Message d'erreur partagé quand PRF n'est pas disponible sur cet authenticator. */
const PRF_UNSUPPORTED =
  "Cet authenticator ne supporte pas l'extension PRF. Sur Windows Hello, " +
  "PRF requiert la mise à jour de février 2026 (build 26200.7840+) avec " +
  'Chrome 147+ ou Edge 146+.';

export interface RegisteredCredential {
  credentialId: string;
  /** Secret PRF si l'authenticator l'a renvoyé dès la création, sinon null. */
  secret: ArrayBuffer | null;
  /** Transports du credential, à rejouer au get() pour fiabiliser le routage. */
  transports: AuthenticatorTransport[];
}

/**
 * Crée un passkey **plateforme** (Windows Hello / Touch ID — lié à cette
 * machine, jamais le téléphone) dédié au wrapping de la clé device.
 *
 * On tente de récupérer directement le secret PRF dès la création (Chrome 147+
 * sur Windows). Sinon on vérifie que PRF est `enabled` et le secret sera obtenu
 * via une cérémonie `get()` ultérieure.
 */
export const registerDeviceWrapCredential = async (
  userId: string,
  userName: string,
): Promise<RegisteredCredential> => {
  if (!isWebAuthnPrfSupported()) {
    throw new Error("WebAuthn indisponible : contexte non sécurisé ou navigateur incompatible.");
  }

  const challenge = crypto.getRandomValues(new Uint8Array(32));
  const credential = (await navigator.credentials.create({
    publicKey: {
      challenge,
      rp: { name: 'secuapp', id: window.location.hostname },
      user: {
        // Prefix évite que ce credential écrase le credential Keycloak dans
        // Windows Hello : les deux ont le même rpId (localhost) mais des userId
        // distincts, donc Windows Hello crée un slot séparé.
        id: new TextEncoder().encode(`secuapp-wrap:${userId}`),
        name: userName,
        displayName: userName,
      },
      pubKeyCredParams: [
        { type: 'public-key', alg: -7 },   // ES256
        { type: 'public-key', alg: -257 }, // RS256
      ],
      authenticatorSelection: {
        // 'platform' = lier au matériel de cette machine (Windows Hello).
        // 'discouraged' : credential non-discoverable → n'apparaît PAS dans le
        // passkey picker de Chrome. Keycloak a son propre passkey discoverable
        // pour l'auth ; si on crée un second credential discoverable ici,
        // Chrome affiche les deux au login Keycloak et l'utilisateur ne voit
        // plus "Windows Hello". PRF fonctionne sans residentKey.
        authenticatorAttachment: 'platform',
        residentKey: 'discouraged',
        requireResidentKey: false,
        userVerification: 'required',
      },
      timeout: 60_000,
      extensions: { prf: { eval: { first: PRF_SALT } } },
    },
  })) as PublicKeyCredential | null;

  if (!credential) {
    throw new Error('Création du passkey annulée.');
  }

  const ext = credential.getClientExtensionResults();
  if (!ext.prf?.enabled) {
    throw new Error(PRF_UNSUPPORTED);
  }

  const attestation = credential.response as AuthenticatorAttestationResponse;
  const transports = typeof attestation.getTransports === 'function'
    ? (attestation.getTransports() as AuthenticatorTransport[])
    : [];

  const first = ext.prf.results?.first;
  return {
    credentialId: toBase64Url(credential.rawId),
    secret: first ? toArrayBuffer(first) : null,
    transports,
  };
};

/**
 * Rejoue une cérémonie WebAuthn pour récupérer le secret PRF (32 octets) du
 * credential donné. Déclenche la vérification utilisateur (biométrie / PIN).
 *
 * `transports` (stockés à l'enregistrement) aident le navigateur à router la
 * cérémonie vers le bon authenticator (`internal` pour Windows Hello) plutôt
 * que de tenter un flux téléphone/hybride peu fiable.
 */
export const deriveDeviceWrapSecret = async (
  credentialId: string,
  transports: AuthenticatorTransport[] = [],
): Promise<ArrayBuffer> => {
  if (!isWebAuthnPrfSupported()) {
    throw new Error("WebAuthn indisponible : contexte non sécurisé ou navigateur incompatible.");
  }

  const challenge = crypto.getRandomValues(new Uint8Array(32));
  const assertion = (await navigator.credentials.get({
    publicKey: {
      challenge,
      allowCredentials: [{
        type: 'public-key',
        id: fromBase64Url(credentialId),
        ...(transports.length ? { transports } : {}),
      }],
      userVerification: 'required',
      timeout: 60_000,
      extensions: { prf: { eval: { first: PRF_SALT } } },
    },
  })) as PublicKeyCredential | null;

  if (!assertion) {
    throw new Error('Cérémonie WebAuthn annulée.');
  }

  const first = assertion.getClientExtensionResults().prf?.results?.first;
  if (!first) {
    throw new Error(PRF_UNSUPPORTED);
  }
  return toArrayBuffer(first);
};
