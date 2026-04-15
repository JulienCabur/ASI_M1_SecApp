import style from './navbar.module.scss';
import { useNavigate } from 'react-router';
import {
  FaHome,
  FaFolderOpen,
  FaSignOutAlt,
  FaUserMd,
  FaBell,
} from 'react-icons/fa';
import { FaFileMedical } from 'react-icons/fa6';
import { keycloak, stopTokenRefresh } from '@/services/auth.service';

export const NavItem = ({ label, to }: { label: string; to: string }) => {
  const navigate = useNavigate();

  switch (label) {
    case 'Home':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaHome className={style.icon} />
        </div>
      );
    case 'Dossier':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaFileMedical className={style.icon} />
        </div>
      );
    case 'Doctors':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaUserMd className={style.icon} />
        </div>
      );
    case 'Notifications':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaBell className={style.icon} />
        </div>
      );
    case 'Folders':
      return (
        <div className={style.navItem} onClick={() => navigate(to)}>
          <FaFolderOpen className={style.icon} />
        </div>
      );
    case 'Logout':
      return (
        <div
          className={style.navItem}
          onClick={() => {
            stopTokenRefresh();
            keycloak.logout({ redirectUri: window.location.origin + '/' });
          }}
        >
          <FaSignOutAlt className={style.icon} />
        </div>
      );
    default:
      return (
        <div onClick={() => navigate(to)}>{label}</div>
      );
  }
};
