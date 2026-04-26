/**
 * Helpers pour signer un challenge d'authentification avec un certificat .p12.
 *
 * Utilisé par le flow "reset par certificat" côté médecin :
 *   1. backend → challenge { nonce, timestamp }
 *   2. ici : on déchiffre le .p12 (PBE) avec le mot de passe utilisateur,
 *      on extrait clé privée + cert PEM, on signe `${nonce}:${timestamp}`
 *      en RSA-PSS / SHA256 (max salt) — équivalent à la verif Python côté back.
 *   3. front → POST { username, nonce, timestamp, signature(hex), certificate(PEM) }
 */

import forge from 'node-forge';

export interface SignResult {
  signatureHex: string;
  certificatePem: string;
}

const toHex = (bytes: string): string => {
  let out = '';
  for (let i = 0; i < bytes.length; i += 1) {
    out += bytes.charCodeAt(i).toString(16).padStart(2, '0');
  }
  return out;
};

const readFileAsArrayBuffer = (file: File): Promise<ArrayBuffer> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error('Lecture du fichier impossible'));
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.readAsArrayBuffer(file);
  });

export const signChallengeWithP12 = async (
  p12File: File,
  password: string,
  data: string,
): Promise<SignResult> => {
  const buffer = await readFileAsArrayBuffer(p12File);
  const der = forge.util.createBuffer(buffer as unknown as forge.util.ByteStringBuffer | ArrayBuffer);
  const asn1 = forge.asn1.fromDer(der);
  const p12 = forge.pkcs12.pkcs12FromAsn1(asn1, false, password);

  const keyBags = p12.getBags({ bagType: forge.pki.oids.pkcs8ShroudedKeyBag })[forge.pki.oids.pkcs8ShroudedKeyBag] ?? [];
  const certBags = p12.getBags({ bagType: forge.pki.oids.certBag })[forge.pki.oids.certBag] ?? [];

  const privateKey = keyBags[0]?.key;
  const certificate = certBags[0]?.cert;
  if (!privateKey || !certificate) {
    throw new Error('Certificat ou clé privée introuvable dans le .p12');
  }

  const md = forge.md.sha256.create();
  md.update(data, 'utf8');

  // RSA-PSS / SHA-256 / MGF1(SHA-256) / salt = hash length (équivalent à PSS.MAX_LENGTH côté back).
  const pss = forge.pss.create({
    md: forge.md.sha256.create(),
    mgf: forge.mgf.mgf1.create(forge.md.sha256.create()),
    saltLength: 32,
  });

  const signatureBytes = (privateKey as forge.pki.rsa.PrivateKey).sign(md, pss);
  const certificatePem = forge.pki.certificateToPem(certificate);

  return {
    signatureHex: toHex(signatureBytes),
    certificatePem,
  };
};
