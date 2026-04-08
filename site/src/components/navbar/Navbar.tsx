import { Badge } from 'antd';
import { useNavigate } from 'react-router';
import { FaBell } from 'react-icons/fa';
import style from './navbar.module.scss';
import { NavItem } from './NavItem';
import { useNotificationsStore } from '@/store/notifications.store';

const Navbar = () => {
  const navigate = useNavigate();
  const pendingCount = useNotificationsStore((s) => s.pendingCount);

  return (
    <div className={style.navbar}>
      <div className={style.links}>
        <NavItem label="Home" to="/" />
        <NavItem label="Dossier" to="/dossier" />
        <NavItem label="Doctors" to="/doctors" />
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
