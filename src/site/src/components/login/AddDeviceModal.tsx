import { useState } from 'react';
import { Alert, Button, Form, Input, Modal, message } from 'antd';
import { MobileOutlined, MailOutlined } from '@ant-design/icons';
import { requestAddDevice } from '@/services/auth.service';

interface AddDeviceValues {
  email: string;
}

interface AddDeviceModalProps {
  open: boolean;
  onClose: () => void;
}

const AddDeviceModal: React.FC<AddDeviceModalProps> = ({ open, onClose }) => {
  const [form] = Form.useForm<AddDeviceValues>();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const close = () => {
    form.resetFields();
    setSubmitted(false);
    onClose();
  };

  const handleSubmit = async ({ email }: AddDeviceValues) => {
    setSubmitting(true);
    try {
      await requestAddDevice(email);
      setSubmitted(true);
    } catch {
      message.error('Impossible de contacter le serveur. Réessayez dans un instant.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title={
        <span>
          <MobileOutlined style={{ marginRight: 8 }} />
          Enregistrer cet appareil
        </span>
      }
      open={open}
      onCancel={close}
      footer={
        submitted
          ? [<Button key="ok" type="primary" onClick={close}>Fermer</Button>]
          : [
              <Button key="cancel" onClick={close}>Annuler</Button>,
              <Button key="ok" type="primary" loading={submitting} onClick={() => form.submit()}>
                Envoyer le lien
              </Button>,
            ]
      }
      destroyOnHidden
    >
      {submitted ? (
        <Alert
          type="success"
          showIcon
          message="Si un compte correspond à cette adresse, un lien d'enregistrement vient d'y être envoyé."
          description="Cliquez sur le lien dans l'email pour enregistrer votre empreinte ou clé de sécurité sur cet appareil. Une fois l'enregistrement terminé, vous serez redirigé ici pour finaliser la connexion. Vos autres appareils ne sont pas affectés."
        />
      ) : (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Premier accès sur cet appareil"
            description="Votre clé d'accès (passkey) est liée à votre appareil d'origine. Pour vous connecter ici, vous devez en enregistrer une nouvelle. Entrez votre adresse e-mail et nous vous enverrons un lien d'enregistrement. Vos autres appareils et vos fichiers restent accessibles."
          />
          <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false} preserve={false}>
            <Form.Item
              name="email"
              label="Adresse e-mail"
              rules={[{ required: true, message: 'E-mail requis' }]}
            >
              <Input prefix={<MailOutlined />} placeholder="vous@example.com" autoFocus />
            </Form.Item>
          </Form>
        </>
      )}
    </Modal>
  );
};

export default AddDeviceModal;
