import { useState } from 'react';
import { Alert, DatePicker, Form, Input, Modal, message } from 'antd';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { registerDoctor } from '@/services/auth.service';

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

  const handleSubmit = async (values: CertificateFormValues) => {
    setSubmitting(true);
    try {
      const result = await registerDoctor({
        username: values.username,
        email: values.email,
        first_name: values.first_name,
        last_name: values.last_name,
        date_of_birth: values.date_of_birth.format('YYYY-MM-DD'),
        organization: values.organization.trim(),
      });
      triggerP12Download(result.certificate_b64, result.filename);
      onIssued({ filename: result.filename, password: result.password });
      form.resetFields();
      onClose();
    } catch (err) {
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
        description="La génération peut prendre une dizaine de secondes (CSR, signature, création du compte). Ne fermez pas la fenêtre."
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
          label="Organisation"
          rules={[
            { required: true, message: 'Organisation requise' },
            { max: 120, message: '120 caractères maximum' },
          ]}
        >
          <Input placeholder="Hôpital Saint-Pierre" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default DoctorRegistrationModal;
