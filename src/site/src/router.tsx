import { BrowserRouter, Outlet, Route, Routes } from 'react-router';
import style from './router.module.scss';
import { RequireAuth } from '@/components/auth/RequireAuth';
import Navbar from '@/components/navbar/Navbar';
import { Home } from '@/pages/home/Home';
import Login from '@/pages/login/Login';
import AuthCallback from '@/pages/auth/AuthCallback';
import Doctors from '@/pages/doctors/Doctors';
import Dossier from '@/pages/dossier/Dossier';
import Notifications from '@/pages/notifications/Notifications';
import Devices from '@/pages/devices/Devices';

const MainLayout = () => {
  return (
    <>
      <Navbar />
      <div className={style.content}>
        <Outlet />
      </div>
    </>
  );
};

const Router = () => {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes — no auth required */}
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />

        {/* Protected routes */}
        <Route element={<RequireAuth />}>
          <Route element={<MainLayout />}>
            <Route path="/" element={<Home />} />
            <Route path="/dossier" element={<Dossier />} />
            <Route path="/doctors" element={<Doctors />} />
            <Route path="/notifications" element={<Notifications />} />
            <Route path="/devices" element={<Devices />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default Router;
