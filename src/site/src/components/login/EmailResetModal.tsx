import { useState } from 'react';
import { Alert, Button, Form, Input, Modal, message } from 'antd';
import { MailOutlined } from '@ant-design/icons';
import { requestCredentialsReset } from '@/services/auth.service';

interface EmailResetValues {
  email: string;
}

interface EmailResetModalProps {
  open: boolean;
  onClose: () => void;
}

const EmailResetModal: React.FC<EmailResetModalProps> = ({ open, onClose }) => {
  const [form] = Form.useForm<EmailResetValues>();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const close = () => {
    form.resetFields();
    setSubmitted(false);
    onClose();
  };

  const handleSubmit = async ({ email }: EmailResetValues) => {
    setSubmitting(true);
    try {
      await requestCredentialsReset(email);
      setSubmitted(true);
    } catch {
      // Le back répond toujours 200 par sécurité (anti-énumération) ;
      // un échec ici signifie un vrai souci réseau.
      message.error('Impossible de contacter le serveur. Réessayez dans un instant.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Réinitialiser ma clé d'accès"
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
          description="Le lien est valable 1 heure. Vous pourrez ré-enrôler votre passkey ou clé de sécurité depuis ce lien."
        />
      ) : (
        <>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
            message="Authentification sans mot de passe"
            description="Cette application utilise une clé d'accès (passkey / WebAuthn). Si vous l'avez perdue, on vous envoie un lien pour en enregistrer une nouvelle."
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

export default EmailResetModal;
