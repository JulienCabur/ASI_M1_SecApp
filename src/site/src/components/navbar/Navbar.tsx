import { Badge } from 'antd';
import { useNavigate } from 'react-router';
import { FaBell } from 'react-icons/fa';
import style from './navbar.module.scss';
import { NavItem } from './NavItem';
import { useNotificationsStore } from '@/store/notifications.store';
import { useAuth } from '@/hooks/useAuth';

const Navbar = () => {
  const navigate = useNavigate();
  const pendingCount = useNotificationsStore((s) => s.pendingCount);
  const { role } = useAuth();
  const isDoctor = role === 'role_docteurs';

  return (
    <div className={style.navbar}>
      <div className={style.links}>
        <NavItem label="Home" to="/" />
        {isDoctor ? (
          <NavItem label="Patients" to="/patients" />
        ) : (
          <>
            <NavItem label="Dossier" to="/dossier" />
            <NavItem label="Doctors" to="/doctors" />
          </>
        )}
        <NavItem label="Devices" to="/devices" />
        <NavItem label="Logout" to="/logout" />
      </div>

      <div className={style.bottom}>
        <Badge count={pendingCount} overflowCount={99} offset={[-4, 4]}>
          <div className={style.navItem} onClick={() => navigate('/notifications')}>
            <FaBell className={style.icon} />
          </div>
        </Badge>
      </div>
    </div>
  );
};

export default Navbar;
