import { useAuth } from '@/hooks/useAuth';
import PatientDashboard from './PatientDashboard';
import DoctorDashboard from './DoctorDashboard';

export const Home: React.FC = () => {
  const { role } = useAuth();

  if (role === 'role_docteurs') return <DoctorDashboard />;
  return <PatientDashboard />;
};
