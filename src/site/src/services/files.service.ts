/**
 * Service fichiers — chiffrement de bout en bout.
 *
 * Modèle d'envelope :
 *  - DEK AES-GCM 256 fraîche par fichier (jamais réutilisée), tirée par
 *    crypto.service.ts.
 *  - Le DEK est wrappé par la KEK de session, donc seul le détenteur de la
 *    privée RSA (et donc de la KEK) peut décoder le fichier.
 *  - Le backend stocke un seul champ `ciphered_dek` par fichier ; on y met
 *    une enveloppe JSON-puis-base64 contenant `{ fileIv, wrappedDek, dekIv }`.
 *  - Le contenu chiffré (AES-GCM) est envoyé comme corps multipart classique.
 *
 * Le serveur n'a donc accès qu'à du ciphertext opaque + une enveloppe
 * inutilisable sans la KEK : confidentialité de bout en bout, indépendamment
 * du fait qu'un admin DB puisse lire les lignes.
 */

import { api } from '@/services/api';
import {
  decryptFileWithKEK,
  encryptFileWithKEK,
  type EncryptedFile,
} from '@/services/crypto.service';
import { useCryptoStore } from '@/store/crypto.store';

export interface RemoteFile {
  name: string;
  date: string;
  cipheredDek: string;
}

interface ListFilesResponse {
  files: { name: string; date: string; ciphered_dek: string }[];
}

interface DownloadResponse {
  file_content: string; // base64 du ciphertext stocké côté serveur
  key: string;          // enveloppe (JSON-base64) telle qu'envoyée à l'upload
  filename: string;
}

interface DekEnvelope {
  fileIv: string;
  wrappedDek: string;
  dekIv: string;
}

const toBase64 = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let bin = '';
  for (let i = 0; i < bytes.byteLength; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
};

const fromBase64 = (b64: string): ArrayBuffer => {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes.buffer;
};

const encodeEnvelope = (enc: Pick<EncryptedFile, 'fileIv' | 'wrappedDek' | 'dekIv'>): string =>
  btoa(
    JSON.stringify({
      fileIv: toBase64(enc.fileIv),
      wrappedDek: toBase64(enc.wrappedDek),
      dekIv: toBase64(enc.dekIv),
    } satisfies DekEnvelope),
  );

const decodeEnvelope = (
  encoded: string,
): Pick<EncryptedFile, 'fileIv' | 'wrappedDek' | 'dekIv'> => {
  const json = JSON.parse(atob(encoded)) as DekEnvelope;
  return {
    fileIv: fromBase64(json.fileIv),
    wrappedDek: fromBase64(json.wrappedDek),
    dekIv: fromBase64(json.dekIv),
  };
};

const requireKek = (): CryptoKey => {
  const kek = useCryptoStore.getState().kek;
  if (!kek) {
    throw new Error('Session crypto non initialisée — clé KEK absente.');
  }
  return kek;
};

export const listFiles = async (): Promise<RemoteFile[]> => {
  const { data } = await api.get<ListFilesResponse>('/files/list_files');
  return data.files.map((f) => ({
    name: f.name,
    date: f.date,
    cipheredDek: f.ciphered_dek,
  }));
};

export const uploadFile = async (file: File): Promise<void> => {
  const kek = requireKek();
  const plain = await file.arrayBuffer();
  const enc = await encryptFileWithKEK(plain, kek);
  const envelope = encodeEnvelope(enc);

  const form = new FormData();
  // Le 3e argument fixe le nom de fichier côté backend, on garde l'original.
  form.append('file', new Blob([enc.ciphertext]), file.name);
  await api.post('/files/upload_file', form, {
    params: { dek: envelope },
  });
};

export interface DecryptedFile {
  blob: Blob;
  filename: string;
}

const guessMimeType = (filename: string): string => {
  const ext = filename.split('.').pop()?.toLowerCase() ?? '';
  switch (ext) {
    case 'pdf': return 'application/pdf';
    case 'png': return 'image/png';
    case 'jpg':
    case 'jpeg': return 'image/jpeg';
    case 'gif': return 'image/gif';
    case 'webp': return 'image/webp';
    case 'svg': return 'image/svg+xml';
    case 'txt': return 'text/plain';
    case 'json': return 'application/json';
    default: return 'application/octet-stream';
  }
};

export const downloadFile = async (name: string): Promise<DecryptedFile> => {
  const kek = requireKek();
  const { data } = await api.get<DownloadResponse>('/files/download_file', {
    params: { file: name },
  });
  const env = decodeEnvelope(data.key);
  const plain = await decryptFileWithKEK(
    {
      ciphertext: fromBase64(data.file_content),
      ...env,
    },
    kek,
  );
  return {
    blob: new Blob([plain], { type: guessMimeType(data.filename) }),
    filename: data.filename,
  };
};

export const deleteFile = async (name: string): Promise<void> => {
  await api.post('/files/delete_file', null, { params: { file: name } });
};
