/**
 * CryptoService — primitives cryptographiques côté navigateur.
 *
 * Posture sécurité :
 *  - La paire est générée avec `extractable: false`. Pour RSA, la spec
 *    WebCrypto force la clé publique à rester extractable malgré ce flag,
 *    donc seule la privée devient un handle opaque : `exportKey()` lèvera
 *    `InvalidAccessError`. Aucun JS (ni XSS, ni extension) ne peut lire
 *    la matière clé.
 *  - La privée est persistée dans IndexedDB via structured clone. Elle
 *    survit au reload mais reste cloisonnée à l'origine et inaccessible
 *    en clair.
 */


/**--------------------------------------------------------------
 RSA KEY
 --------------------------------------------------------------*/
const DB_NAME = 'secuapp-keystore';
const DB_VERSION = 1;
const STORE_NAME = 'keys';
const PRIVATE_KEY_ID = 'user-private-key';
const PUBLIC_KEY_ID = 'user-public-key';

const openDb = (): Promise<IDBDatabase> =>
    new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME);
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error ?? new Error('IndexedDB indisponible'));
    });

const withStore = async <T>(
    mode: IDBTransactionMode,
    operation: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> => {
    const db = await openDb();
    try {
        return await new Promise<T>((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, mode);
            const request = operation(tx.objectStore(STORE_NAME));
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error ?? new Error('Opération IndexedDB échouée'));
        });
    } finally {
        db.close();
    }
};

export const generateKeyPair = async (): Promise<CryptoKeyPair> => {
    return await crypto.subtle.generateKey(
        {
            name: "RSA-OAEP",
            modulusLength: 4096,
            publicExponent: new Uint8Array([1, 0, 1]),
            hash: "SHA-512",
        },
        false,
        ["encrypt", "decrypt", "wrapKey", "unwrapKey"]
    );
}

export const savePrivateKey = async (privateKey: CryptoKey): Promise<void> => {
    if (privateKey.extractable) {
        throw new Error('Refus de persister une clé privée extractable.');
    }
    await withStore('readwrite', (store) => store.put(privateKey, PRIVATE_KEY_ID));
};

export const loadPrivateKey = async (): Promise<CryptoKey | null> => {
    const result = await withStore<CryptoKey | undefined>(
        'readonly',
        (store) => store.get(PRIVATE_KEY_ID) as IDBRequest<CryptoKey | undefined>,
    );
    return result ?? null;
};

export const hasPrivateKey = async (): Promise<boolean> => {
    const count = await withStore<number>(
        'readonly',
        (store) => store.count(PRIVATE_KEY_ID),
    );
    return count > 0;
};

export const clearPrivateKey = async (): Promise<void> => {
    await withStore('readwrite', (store) => store.delete(PRIVATE_KEY_ID));
};

export const savePublicKey = async (publicKey: CryptoKey): Promise<void> => {
    if (publicKey.type !== 'public') {
        throw new Error('savePublicKey attend une CryptoKey publique.');
    }
    await withStore('readwrite', (store) => store.put(publicKey, PUBLIC_KEY_ID));
};

export const loadPublicKey = async (): Promise<CryptoKey | null> => {
    const result = await withStore<CryptoKey | undefined>(
        'readonly',
        (store) => store.get(PUBLIC_KEY_ID) as IDBRequest<CryptoKey | undefined>,
    );
    return result ?? null;
};

export const clearPublicKey = async (): Promise<void> => {
    await withStore('readwrite', (store) => store.delete(PUBLIC_KEY_ID));
};

export const exportPublicKeyJwk = async (publicKey: CryptoKey): Promise<JsonWebKey> =>
    crypto.subtle.exportKey('jwk', publicKey);


/**--------------------------------------------------------------
 * KEK (Key Encryption Key) — envelope encryption
 --------------------------------------------------------------*/

export interface SealedKek {
    kek: CryptoKey;
    wrappedKek: ArrayBuffer; 
    
}

export const generateKEKFromRSAKey = async (publicKey: CryptoKey): Promise<SealedKek> => {
    if (publicKey.type !== 'public') {
        throw new Error('generateKEKFromRSAKey attend une clé publique RSA-OAEP.');
    }
    const kek = await crypto.subtle.generateKey(
        {
            name: 'AES-GCM',
            length: 256,
        },
        true,
        ['wrapKey', 'unwrapKey']
    );
    const wrappedKek = await crypto.subtle.wrapKey(
        'raw',
        kek,
        publicKey,
        { name: 'RSA-OAEP' },
    );
    return { kek, wrappedKek };
};

export const unwrapKEKWithRSAKey = async (
    wrappedKek: ArrayBuffer,
    privateKey: CryptoKey,
): Promise<CryptoKey> => {
    if (privateKey.type !== 'private') {
        throw new Error('unwrapKEKWithRSAKey attend une clé privée RSA-OAEP.');
    }
    return crypto.subtle.unwrapKey(
        'raw',
        wrappedKek,
        privateKey,
        { name: 'RSA-OAEP' },
        { name: 'AES-GCM', length: 256 },
        false,
        ['wrapKey', 'unwrapKey'],
    );
};

/**---------------------------------------------------------------------------------------
 * Chiffrement de fichier avec DEK (Data Encryption Key) symétrique protégée par KEK
 *
 * Pour chaque fichier on tire un DEK AES-GCM 256 frais (jamais réutilisé),
 * on chiffre le contenu, puis on wrap le DEK avec la KEK. Le bundle résultat
 * contient tout le nécessaire pour déchiffrer si on possède la KEK.
 ---------------------------------------------------------------------------------------*/

export interface EncryptedFile {
    ciphertext: ArrayBuffer;
    fileIv: ArrayBuffer;     // 12 octets, IV AES-GCM du chiffrement fichier
    wrappedDek: ArrayBuffer; // DEK chiffré par la KEK
    dekIv: ArrayBuffer;      // 12 octets, IV AES-GCM utilisé pour wrap le DEK
}

const randomIv = (): ArrayBuffer => {
    const buf = new ArrayBuffer(12);
    crypto.getRandomValues(new Uint8Array(buf));
    return buf;
};

export const encryptFileWithKEK = async (
    data: ArrayBuffer,
    kek: CryptoKey,
): Promise<EncryptedFile> => {
    if (kek.type !== 'secret' || (kek.algorithm as AesKeyAlgorithm).name !== 'AES-GCM') {
        throw new Error('encryptFileWithKEK attend une KEK AES-GCM.');
    }
    if (!kek.usages.includes('wrapKey')) {
        throw new Error('La KEK doit avoir l\'usage "wrapKey".');
    }

    const dek = await crypto.subtle.generateKey(
        { name: 'AES-GCM', length: 256 },
        true, // extractable obligatoire pour le wrap ci-dessous
        ['encrypt', 'decrypt'],
    );

    const fileIv = randomIv();
    const ciphertext = await crypto.subtle.encrypt(
        { name: 'AES-GCM', iv: fileIv },
        dek,
        data,
    );

    const dekIv = randomIv();
    const wrappedDek = await crypto.subtle.wrapKey(
        'raw',
        dek,
        kek,
        { name: 'AES-GCM', iv: dekIv },
    );

    return { ciphertext, fileIv, wrappedDek, dekIv };
};

export const decryptFileWithKEK = async (
    encrypted: EncryptedFile,
    kek: CryptoKey,
): Promise<ArrayBuffer> => {
    if (!kek.usages.includes('unwrapKey')) {
        throw new Error('La KEK doit avoir l\'usage "unwrapKey".');
    }

    const dek = await crypto.subtle.unwrapKey(
        'raw',
        encrypted.wrappedDek,
        kek,
        { name: 'AES-GCM', iv: encrypted.dekIv },
        { name: 'AES-GCM', length: 256 },
        false, // DEK reconstruit non-extractable
        ['decrypt'],
    );

    return crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: encrypted.fileIv },
        dek,
        encrypted.ciphertext,
    );
};