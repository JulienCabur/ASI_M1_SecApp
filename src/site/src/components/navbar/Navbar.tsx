import { useEffect, useRef, useState } from 'react';
import { Badge, notification } from 'antd';
import { useNavigate } from 'react-router';
import { FaBell, FaMobileAlt } from 'react-icons/fa';
import style from './navbar.module.scss';
import { NavItem } from './NavItem';
import { useNotificationsStore } from '@/store/notifications.store';
import { useCryptoStore } from '@/store/crypto.store';
import { listUnverifiedDevices } from '@/services/device.service';

const Navbar = () => {
  const navigate = useNavigate();
  const pendingCount = useNotificationsStore((s) => s.pendingCount);
  const pendingSignal = useCryptoStore((s) => s.pendingSignal);
  const [pendingDevices, setPendingDevices] = useState(0);
  const prevPendingDevices = useRef(0);

  useEffect(() => {
    const refresh = async () => {
      try {
        const devices = await listUnverifiedDevices();
        const count = devices.length;
        if (count > prevPendingDevices.current) {
          notification.warning({
            message: 'Nouvel appareil en attente',
            description: `${count - prevPendingDevices.current} appareil(s) attend(ent) votre approbation.`,
            duration: 6,
            onClick: () => navigate('/devices'),
          });
        }
        prevPendingDevices.current = count;
        setPendingDevices(count);
      } catch {
        // silencieux — session pas encore prête
      }
    };

    void refresh();
  // pendingSignal change à chaque événement SSE device_pending ou reconnexion
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingSignal]);

  return (
    <div className={style.navbar}>
      <div className={style.links}>
        <NavItem label="Home" to="/" />
        <NavItem label="Dossier" to="/dossier" />
        <NavItem label="Doctors" to="/doctors" />
        <Badge count={pendingDevices} overflowCount={9} offset={[-4, 4]}>
          <div className={style.navItem} onClick={() => navigate('/devices')}>
            <FaMobileAlt className={style.icon} />
          </div>
        </Badge>
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
