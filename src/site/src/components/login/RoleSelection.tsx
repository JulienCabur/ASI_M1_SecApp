import { Card, Typography } from 'antd';
import { MedicineBoxOutlined, UserOutlined } from '@ant-design/icons';
import style from './login.module.scss';

const { Title, Text } = Typography;

export type RoleChoice = 'patient' | 'doctor';

interface RoleSelectionProps {
  onSelect: (role: RoleChoice) => void;
}

const RoleSelection: React.FC<RoleSelectionProps> = ({ onSelect }) => (
  <div className={style.tiles}>
    <Card hoverable className={style.tile} onClick={() => onSelect('patient')}>
      <UserOutlined className={style.icon} />
      <Title level={3} style={{ margin: 0 }}>Patient</Title>
      <Text type="secondary">Accéder à mon dossier médical</Text>
    </Card>
    <Card hoverable className={style.tile} onClick={() => onSelect('doctor')}>
      <MedicineBoxOutlined className={style.icon} />
      <Title level={3} style={{ margin: 0 }}>Médecin</Title>
      <Text type="secondary">Accéder à mes patients</Text>
    </Card>
  </div>
);

export default RoleSelection;
