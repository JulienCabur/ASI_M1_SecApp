import { Button, Form, Input, Typography, Card } from 'antd';
import { getRegistrationUrl } from '@/services/auth.service';
import type { RegistrationParams } from '@/services/auth.service';
import style from './register.module.scss';

const { Title, Text } = Typography;

const Register: React.FC = () => {
  const [form] = Form.useForm<RegistrationParams & { role: string }>();

  const handleSubmit = async (values: RegistrationParams) => {
    const url = await getRegistrationUrl(values);
    window.location.href = url;
  };

  return (
    <div className={style.container}>
      <Card className={style.card}>
        <div className={style.header}>
          <Title level={2} style={{ margin: 0 }}>Créer un compte</Title>
          <Text type="secondary">Renseignez vos informations pour vous inscrire</Text>
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          requiredMark={false}
        >
          <div className={style.nameRow}>
            <Form.Item
              name="firstName"
              label="Prénom"
              rules={[{ required: true, message: 'Prénom requis' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="Jean" size="large" />
            </Form.Item>

            <Form.Item
              name="lastName"
              label="Nom"
              rules={[{ required: true, message: 'Nom requis' }]}
              style={{ flex: 1 }}
            >
              <Input placeholder="Dupont" size="large" />
            </Form.Item>
          </div>

          <Form.Item
            name="email"
            label="Adresse e-mail"
            rules={[
              { required: true, message: 'E-mail requis' },
              { type: 'email', message: 'Adresse e-mail invalide' },
            ]}
          >
            <Input placeholder="jean.dupont@example.com" size="large" />
          </Form.Item>

          {/* No password field — password is set directly on Keycloak's registration page */}

          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large">
              S'inscrire
            </Button>
          </Form.Item>
        </Form>

        <div className={style.footer}>
          <Text>Déjà un compte ?</Text>{' '}
          <a href="/login">Se connecter</a>
        </div>
      </Card>
    </div>
  );
};

export default Register;
