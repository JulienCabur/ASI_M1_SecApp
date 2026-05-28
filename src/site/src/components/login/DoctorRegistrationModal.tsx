import { useEffect, useState } from 'react';
import { Alert, DatePicker, Form, Input, Modal, Select, message } from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { registerDoctor } from '@/services/auth.service';
import { ApiError } from '@/services/api';
import {
  buildP12,
  generateBrowserKeypairAndCsr,
  generateP12Password,
} from '@/services/certificate.service';
import { listHospitals } from '@/services/hospitals.service';

export interface CertificateIssued {
  filename: string;
  password: string;
}

interface CertificateFormValues {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  date_of_birth: Dayjs;
  organization: string;
}

interface DoctorRegistrationModalProps {
  open: boolean;
  onClose: () => void;
  onIssued: (cert: CertificateIssued) => void;
}

// Décode le base64 du .p12 et déclenche un download navigateur — pas de
// persistance disque/JS du binaire ni du mot de passe.
const triggerP12Download = (b64: string, filename: string): void => {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], { type: 'application/x-pkcs12' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const DoctorRegistrationModal: React.FC<DoctorRegistrationModalProps> = ({ open, onClose, onIssued }) => {
  const [form] = Form.useForm<CertificateFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [hospitals, setHospitals] = useState<string[]>([]);
  const [hospitalsLoading, setHospitalsLoading] = useState(false);
  const [hospitalsError, setHospitalsError] = useState<string | null>(null);

  // Charge la liste à l'ouverture de la modale (pas au mount global de l'app).
  // En cas d'échec on bloque le submit : sans la liste, le back rejetterait
  // toute saisie de toute façon (`_assert_known_hospital`).
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setHospitalsLoading(true);
    setHospitalsError(null);
    listHospitals()
      .then((items) => {
        if (cancelled) return;
        setHospitals(items);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = err instanceof Error ? err.message : 'Liste des hôpitaux indisponible';
        setHospitalsError(detail);
      })
      .finally(() => {
        if (!cancelled) setHospitalsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const handleSubmit = async (values: CertificateFormValues) => {
    setSubmitting(true);
    try {
      const organization = values.organization.trim();
      // 1. Génère la paire RSA + le CSR localement. La clé privée reste
      //    dans cette closure ; elle n'est jamais envoyée au back.
      const { csrPem, privateKey } = generateBrowserKeypairAndCsr(
        values.username,
        organization,
      );
      // 2. POST du CSR + métadonnées. Le back valide, fait signer par la PKI,
      //    crée le compte Keycloak et nous renvoie le cert PEM + la chaîne CA.
      const result = await registerDoctor({
        username: values.username,
        email: values.email,
        first_name: values.first_name,
        last_name: values.last_name,
        date_of_birth: values.date_of_birth.format('YYYY-MM-DD'),
        organization,
        csr: csrPem,
      });
      // 3. Assemble le .p12 localement et déclenche le download. Le mot de
      //    passe n'est connu que du navigateur.
      const password = generateP12Password();
      const filename = `${result.username}.p12`;
      const p12Base64 = buildP12({
        privateKey,
        certificatePem: result.certificate_pem,
        caChainPem: result.ca_chain_pem,
        password,
        friendlyName: `Certificat Docteur ${result.username}`,
      });
      triggerP12Download(p12Base64, filename);
      onIssued({ filename, password });
      form.resetFields();
      onClose();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        const body = err.body as { detail?: { field?: string; message?: string } } | null;
        const field = body?.detail?.field;
        const detailMsg = body?.detail?.message ?? err.message;
        if (field === 'username' || field === 'email') {
          form.setFields([{ name: field, errors: [detailMsg] }]);
          return;
        }
        message.error(detailMsg);
        return;
      }
      const detail = err instanceof Error ? err.message : 'Création du certificat impossible';
      message.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Création de certificat"
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="Créer"
      cancelText="Annuler"
      confirmLoading={submitting}
      maskClosable={!submitting}
      closable={!submitting}
      cancelButtonProps={{ disabled: submitting }}
      destroyOnHidden
    >
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Émission par la PKI"
        description="La paire de clés est générée dans votre navigateur — la clé privée ne quitte jamais votre poste. Le certificat est ensuite signé par la PKI puis assemblé localement en .p12. Ne fermez pas la fenêtre."
      />
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        requiredMark={false}
        preserve={false}
        disabled={submitting}
      >
        <Form.Item
          name="username"
          label="Nom d'utilisateur"
          rules={[{ required: true, message: "Nom d'utilisateur requis" }]}
        >
          <Input placeholder="jdupont" />
        </Form.Item>
        <Form.Item
          name="email"
          label="Adresse e-mail"
          rules={[
            { required: true, message: 'E-mail requis' },
            { type: 'email', message: 'Adresse e-mail invalide' },
          ]}
        >
          <Input placeholder="jean.dupont@example.com" />
        </Form.Item>
        <Form.Item
          name="first_name"
          label="Prénom"
          rules={[{ required: true, message: 'Prénom requis' }]}
        >
          <Input placeholder="Jean" />
        </Form.Item>
        <Form.Item
          name="last_name"
          label="Nom"
          rules={[{ required: true, message: 'Nom requis' }]}
        >
          <Input placeholder="Dupont" />
        </Form.Item>
        <Form.Item
          name="date_of_birth"
          label="Date de naissance"
          rules={[
            { required: true, message: 'Date de naissance requise' },
            {
              validator: (_, value: Dayjs | undefined) => {
                if (!value) return Promise.resolve();
                if (value.isAfter(dayjs(), 'day')) {
                  return Promise.reject(new Error('La date doit être dans le passé'));
                }
                if (value.isBefore(dayjs('1900-01-01'), 'day')) {
                  return Promise.reject(new Error('Date invalide'));
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <DatePicker
            style={{ width: '100%' }}
            format="DD/MM/YYYY"
            placeholder="JJ/MM/AAAA"
            disabledDate={(d) => d.isAfter(dayjs(), 'day')}
          />
        </Form.Item>
        <Form.Item
          name="organization"
          label="Hôpital de rattachement"
          rules={[
            { required: true, message: 'Hôpital requis' },
            {
              validator: (_, value: string | undefined) => {
                // Garde-fou : seules les valeurs présentes dans le référentiel
                // chargé peuvent être soumises. Le back revérifie de toute
                // façon, c'est un signal UX précoce pour l'utilisateur.
                if (!value) return Promise.resolve();
                if (!hospitals.includes(value)) {
                  return Promise.reject(new Error('Hôpital hors référentiel'));
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Select
            placeholder={hospitalsLoading ? 'Chargement…' : 'Sélectionner un hôpital'}
            loading={hospitalsLoading}
            disabled={hospitalsLoading || hospitalsError !== null}
            showSearch
            optionFilterProp="label"
            options={hospitals.map((h) => ({ label: h, value: h }))}
            notFoundContent={hospitalsError ? 'Référentiel indisponible' : 'Aucun hôpital'}
          />
        </Form.Item>
        {hospitalsError && (
          <Alert
            type="error"
            showIcon
            style={{ marginBottom: 8 }}
            message="Impossible de charger la liste des hôpitaux"
            description={hospitalsError}
          />
        )}
      </Form>
    </Modal>
  );
};

export default DoctorRegistrationModal;
