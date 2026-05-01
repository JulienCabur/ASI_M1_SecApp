import { useEffect, useState } from 'react';
import { Alert, Button, Card, Descriptions, Space, Tag, Typography, message } from 'antd';
import {
  clearPrivateKey,
  clearPublicKey,
  exportPublicKeyJwk,
  generateKEKFromRSAKey,
  generateKeyPair,
  hasPrivateKey,
  loadPrivateKey,
  loadPublicKey,
  savePrivateKey,
  savePublicKey,
  unwrapKEKWithRSAKey,
} from '@/services/crypto.service';
import style from './crypto-lab.module.scss';

const { Title, Text, Paragraph } = Typography;

const toBase64 = (buf: ArrayBuffer): string => {
  const bytes = new Uint8Array(buf);
  let binary = '';
  bytes.forEach((b) => {
    binary += String.fromCharCode(b);
  });
  return btoa(binary);
};

const CryptoLab: React.FC = () => {
  const [publicKey, setPublicKey] = useState<CryptoKey | null>(null);
  const [privateKey, setPrivateKey] = useState<CryptoKey | null>(null);
  const [publicJwk, setPublicJwk] = useState<JsonWebKey | null>(null);
  const [privateExportError, setPrivateExportError] = useState<string | null>(null);
  const [stored, setStored] = useState<boolean>(false);
  const [busy, setBusy] = useState<boolean>(false);

  const [kek, setKek] = useState<CryptoKey | null>(null);
  const [wrappedKek, setWrappedKek] = useState<ArrayBuffer | null>(null);
  const [unwrappedKek, setUnwrappedKek] = useState<CryptoKey | null>(null);
  const [kekExportError, setKekExportError] = useState<string | null>(null);

  const refreshStored = async () => {
    setStored(await hasPrivateKey());
  };

  useEffect(() => {
    refreshStored();
  }, []);

  const handleGenerate = async () => {
    setBusy(true);
    setPrivateExportError(null);
    try {
      const pair = await generateKeyPair();
      setPublicKey(pair.publicKey);
      setPrivateKey(pair.privateKey);

      const jwk = await exportPublicKeyJwk(pair.publicKey);
      setPublicJwk(jwk);

      // Tentative d'export de la privée — DOIT échouer
      try {
        await crypto.subtle.exportKey('jwk', pair.privateKey);
        setPrivateExportError('⚠️ Anomalie : la clé privée a pu être exportée !');
      } catch (err) {
        setPrivateExportError(
          `Export refusé par le navigateur : ${(err as Error).name} — ${(err as Error).message}`,
        );
      }

      message.success('Paire RSA-OAEP 4096 générée');
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleSave = async () => {
    if (!privateKey || !publicKey) return;
    setBusy(true);
    try {
      await savePrivateKey(privateKey);
      await savePublicKey(publicKey);
      await refreshStored();
      message.success('Paire persistée dans IndexedDB');
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleLoadPublic = async () => {
    setBusy(true);
    try {
      const loaded = await loadPublicKey();
      if (!loaded) {
        message.warning('Aucune clé publique enregistrée');
        return;
      }
      setPublicKey(loaded);
      const jwk = await exportPublicKeyJwk(loaded);
      setPublicJwk(jwk);
      message.success(
        `Publique chargée — usages: ${loaded.usages.join(', ')}`,
      );
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleLoad = async () => {
    setBusy(true);
    try {
      const loaded = await loadPrivateKey();
      if (!loaded) {
        message.warning('Aucune clé privée enregistrée');
      } else {
        setPrivateKey(loaded);
        message.success(
          `Clé chargée — extractable: ${loaded.extractable}, usages: ${loaded.usages.join(', ')}`,
        );
      }
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleClear = async () => {
    setBusy(true);
    try {
      await clearPrivateKey();
      await clearPublicKey();
      setPrivateKey(null);
      setPublicKey(null);
      setPublicJwk(null);
      await refreshStored();
      message.success('Paire effacée');
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleGenerateKek = async () => {
    if (!publicKey) return;
    setBusy(true);
    setKekExportError(null);
    setUnwrappedKek(null);
    try {
      const sealed = await generateKEKFromRSAKey(publicKey);
      setKek(sealed.kek);
      setWrappedKek(sealed.wrappedKek);
      message.success('KEK AES-GCM 256 générée et scellée par RSA-OAEP');
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  const handleUnwrapKek = async () => {
    if (!wrappedKek || !privateKey) return;
    setBusy(true);
    setKekExportError(null);
    try {
      const recovered = await unwrapKEKWithRSAKey(wrappedKek, privateKey);
      setUnwrappedKek(recovered);

      // Tentative d'export de la KEK reconstruite — DOIT échouer
      try {
        await crypto.subtle.exportKey('raw', recovered);
        setKekExportError('⚠️ Anomalie : la KEK reconstruite a pu être exportée !');
      } catch (err) {
        setKekExportError(
          `Export refusé : ${(err as Error).name} — ${(err as Error).message}`,
        );
      }

      message.success('KEK déballée avec la clé privée');
    } catch (err) {
      message.error(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={style.container}>
      <Title level={2}>Crypto Lab</Title>
      <Paragraph type="secondary">
        Page de démo : génération de paire RSA-OAEP, vérification de la non-extractabilité
        de la clé privée, export de la publique, persistance via IndexedDB.
      </Paragraph>

      <Space wrap>
        <Button type="primary" onClick={handleGenerate} loading={busy}>
          Générer une paire
        </Button>
        <Button onClick={handleSave} disabled={!privateKey || busy}>
          Persister la privée
        </Button>
        <Button onClick={handleLoad} disabled={busy}>
          Recharger la privée
        </Button>
        <Button onClick={handleLoadPublic} disabled={busy}>
          Recharger la publique
        </Button>
        <Button danger onClick={handleClear} disabled={busy}>
          Effacer
        </Button>
        <Tag color={stored ? 'green' : 'default'}>
          IndexedDB : {stored ? 'clé présente' : 'vide'}
        </Tag>
      </Space>

      <Space wrap>
        <Button onClick={handleGenerateKek} disabled={!publicKey || busy}>
          Générer une KEK scellée
        </Button>
        <Button
          onClick={handleUnwrapKek}
          disabled={!wrappedKek || !privateKey || busy}
        >
          Déballer la KEK avec la privée
        </Button>
      </Space>

      {privateKey && (
        <Card title="Clé privée (handle opaque)" className={style.card}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="type">{privateKey.type}</Descriptions.Item>
            <Descriptions.Item label="extractable">
              <Tag color={privateKey.extractable ? 'red' : 'green'}>
                {String(privateKey.extractable)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="algorithm">
              {(privateKey.algorithm as RsaHashedKeyAlgorithm).name} /{' '}
              {(privateKey.algorithm as RsaHashedKeyAlgorithm).modulusLength} bits
            </Descriptions.Item>
            <Descriptions.Item label="usages">{privateKey.usages.join(', ')}</Descriptions.Item>
          </Descriptions>
          {privateExportError && (
            <Alert
              type={privateExportError.startsWith('⚠️') ? 'error' : 'success'}
              message="Tentative d'export de la clé privée"
              description={privateExportError}
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
        </Card>
      )}

      {publicKey && publicJwk && (
        <Card title="Clé publique (exportable)" className={style.card}>
          <Title level={5}>JWK</Title>
          <pre className={style.pre}>{JSON.stringify(publicJwk, null, 2)}</pre>
          <Text type="secondary">
            Cette représentation est destinée à être envoyée au backend.
          </Text>
        </Card>
      )}

      {kek && wrappedKek && (
        <Card title="KEK (Key Encryption Key)" className={style.card}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="algorithm">
              {(kek.algorithm as AesKeyAlgorithm).name} /{' '}
              {(kek.algorithm as AesKeyAlgorithm).length} bits
            </Descriptions.Item>
            <Descriptions.Item label="usages">{kek.usages.join(', ')}</Descriptions.Item>
            <Descriptions.Item label="extractable (mémoire)">
              <Tag color={kek.extractable ? 'orange' : 'green'}>
                {String(kek.extractable)}
              </Tag>
              <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                requis à la génération pour pouvoir wrap
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="taille wrappée">
              {wrappedKek.byteLength} octets ({wrappedKek.byteLength * 8} bits)
            </Descriptions.Item>
          </Descriptions>
          <Title level={5} style={{ marginTop: 16 }}>
            KEK chiffrée par RSA-OAEP (base64)
          </Title>
          <pre className={style.pre}>{toBase64(wrappedKek)}</pre>
          <Text type="secondary">
            C'est cette valeur opaque qui peut être stockée côté serveur ou
            transmise — seul le détenteur de la clé privée peut la déballer.
          </Text>
        </Card>
      )}

      {unwrappedKek && (
        <Card title="KEK reconstruite via la privée" className={style.card}>
          <Descriptions column={1} size="small">
            <Descriptions.Item label="algorithm">
              {(unwrappedKek.algorithm as AesKeyAlgorithm).name} /{' '}
              {(unwrappedKek.algorithm as AesKeyAlgorithm).length} bits
            </Descriptions.Item>
            <Descriptions.Item label="usages">
              {unwrappedKek.usages.join(', ')}
            </Descriptions.Item>
            <Descriptions.Item label="extractable">
              <Tag color={unwrappedKek.extractable ? 'red' : 'green'}>
                {String(unwrappedKek.extractable)}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
          {kekExportError && (
            <Alert
              type={kekExportError.startsWith('⚠️') ? 'error' : 'success'}
              message="Tentative d'export de la KEK reconstruite"
              description={kekExportError}
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
        </Card>
      )}
    </div>
  );
};

export default CryptoLab;
