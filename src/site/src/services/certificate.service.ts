import forge from "node-forge";

export interface SignResult {
  signatureHex: string;
  certificatePem: string;
}

export interface BrowserKeypairCsr {
  // Le PEM du CSR à envoyer au back. La clé privée correspondante reste
  // dans la closure JS de l'appelant ; elle ne doit JAMAIS être sérialisée
  // ni transmise. Le back se contente de faire signer le CSR par la PKI.
  csrPem: string;
  privateKey: forge.pki.rsa.PrivateKey;
  publicKey: forge.pki.rsa.PublicKey;
}

export interface BuildP12Input {
  privateKey: forge.pki.rsa.PrivateKey;
  certificatePem: string;
  // Chaîne PEM (signing-ca + root) renvoyée par le back. node-forge accepte
  // plusieurs PEM concaténés ; on les parse séparément pour les passer au
  // PKCS#12.
  caChainPem: string;
  password: string;
  friendlyName: string;
}

const toHex = (bytes: string): string => {
  let out = "";
  for (let i = 0; i < bytes.length; i += 1) {
    out += bytes.charCodeAt(i).toString(16).padStart(2, "0");
  }
  return out;
};

const readFileAsArrayBuffer = (file: File): Promise<ArrayBuffer> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(reader.error ?? new Error("Lecture du fichier impossible"));
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.readAsArrayBuffer(file);
  });

export const signChallengeWithP12 = async (
  p12File: File,
  password: string,
  data: string,
): Promise<SignResult> => {
  const buffer = await readFileAsArrayBuffer(p12File);
  const der = forge.util.createBuffer(
    buffer as unknown as forge.util.ByteStringBuffer | ArrayBuffer,
  );
  const asn1 = forge.asn1.fromDer(der);
  const p12 = forge.pkcs12.pkcs12FromAsn1(asn1, false, password);

  const keyBags =
    p12.getBags({ bagType: forge.pki.oids.pkcs8ShroudedKeyBag })[
      forge.pki.oids.pkcs8ShroudedKeyBag
    ] ?? [];
  const certBags =
    p12.getBags({ bagType: forge.pki.oids.certBag })[forge.pki.oids.certBag] ??
    [];

  const privateKey = keyBags[0]?.key;
  const certificate = certBags[0]?.cert;
  if (!privateKey || !certificate) {
    throw new Error("Certificat ou clé privée introuvable dans le .p12");
  }

  const md = forge.md.sha256.create();
  md.update(data, "utf8");

  // RSA-PSS / SHA-256 / MGF1(SHA-256) / salt = MAX_LENGTH (cryptography.PSS.MAX_LENGTH côté back).
  // Pour RSA-2048 + SHA-256 : keyBytes(256) − hashLen(32) − 2 = 222.
  const rsaKey = privateKey as forge.pki.rsa.PrivateKey;
  const keyBytes = Math.ceil(rsaKey.n.bitLength() / 8);
  const saltLength = keyBytes - 32 - 2;
  const pss = forge.pss.create({
    md: forge.md.sha256.create(),
    mgf: forge.mgf.mgf1.create(forge.md.sha256.create()),
    saltLength,
  });

  const signatureBytes = rsaKey.sign(md, pss);
  const certificatePem = forge.pki.certificateToPem(certificate);

  return {
    signatureHex: toHex(signatureBytes),
    certificatePem,
  };
};

/** Génère localement une paire RSA 2048 et le CSR PEM associé.
 *
 * Le subject suit exactement la policy de la signing CA (signing-ca.conf,
 * `match_pol`) : DC=be, DC=healthapp, O=<organization>, CN=<commonName>.
 * Si l'un de ces attributs ne matche pas, OpenSSL côté PKI refusera de
 * signer ; et même avant ça, le back compare le CSR au username/organization
 * passés en multipart pour éviter qu'un username "Alice" envoie un CSR avec
 * CN=Bob et obtienne un cert pour Bob. */
export const generateBrowserKeypairAndCsr = (
  commonName: string,
  organization: string,
): BrowserKeypairCsr => {
  const keypair = forge.pki.rsa.generateKeyPair({ bits: 2048, e: 0x10001 });
  const csr = forge.pki.createCertificationRequest();
  csr.publicKey = keypair.publicKey;
  const DOMAIN_COMPONENT_OID = "0.9.2342.19200300.100.1.25";
  const ia5 = forge.asn1.Type.IA5STRING as unknown as forge.asn1.Class;
  const utf8 = forge.asn1.Type.UTF8 as unknown as forge.asn1.Class;
  csr.setSubject([
    {
      type: DOMAIN_COMPONENT_OID,
      shortName: "DC",
      value: "be",
      valueTagClass: ia5,
    },
    {
      type: DOMAIN_COMPONENT_OID,
      shortName: "DC",
      value: "healthapp",
      valueTagClass: ia5,
    },
    { name: "organizationName", value: organization, valueTagClass: utf8 },
    { name: "commonName", value: commonName, valueTagClass: utf8 },
  ]);
  // SHA-256 : la policy PKI exige `default_md = sha256`. MD5/SHA-1 seraient
  // refusés à la signature.
  csr.sign(keypair.privateKey, forge.md.sha256.create());

  return {
    csrPem: forge.pki.certificationRequestToPem(csr),
    privateKey: keypair.privateKey,
    publicKey: keypair.publicKey,
  };
};

/** Assemble un PKCS#12 (binaire) à partir du cert signé + clé privée + chaîne CA.
 *
 * On utilise AES-256 pour chiffrer la clé privée (au lieu du legacy 3DES par
 * défaut de node-forge) — c'est ce qu'attendent les keystores modernes et ce
 * que produit `openssl pkcs12 -export` sur les distributions récentes.
 *
 * Retourne le .p12 sous forme de base64 directement utilisable pour déclencher
 * un download blob. */
export const buildP12 = (input: BuildP12Input): string => {
  const certificate = forge.pki.certificateFromPem(input.certificatePem);

  const caCerts = (
    input.caChainPem.match(
      /-----BEGIN CERTIFICATE-----[\s\S]*?-----END CERTIFICATE-----/g,
    ) ?? []
  ).map((pem) => forge.pki.certificateFromPem(pem));

  const p12Asn1 = forge.pkcs12.toPkcs12Asn1(
    input.privateKey,
    [certificate, ...caCerts],
    input.password,
    {
      algorithm: "aes256",
      friendlyName: input.friendlyName,
      generateLocalKeyId: true,
    },
  );

  const der = forge.asn1.toDer(p12Asn1).getBytes();
  return forge.util.encode64(der);
};

/** Mot de passe aléatoire pour le .p12 — entropie ≥ 128 bits.
 *  Caractères url-safe pour faciliter le copier/coller depuis l'UI. */
export const generateP12Password = (): string => {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  // base64url sans padding : 24 octets → 32 caractères, exactement comme
  // ce que produisait le script PKI côté serveur (cohérence d'UX).
  let bin = "";
  for (let i = 0; i < bytes.length; i += 1)
    bin += String.fromCharCode(bytes[i]);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};
