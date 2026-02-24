import { BrowserRouter, Outlet, Route, Routes } from "react-router";
import style from './router.module.scss';
import { RequireAuth } from "./components/auth/RequireAuth";
import Navbar from "./components/navbar/Navbar";
import Folders from "./pages/folders/Folders";
import { Home } from "./pages/home/Home";


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


const router = () => {
    return (
        <BrowserRouter>
            <Routes>
                <Route element={<RequireAuth />}>
                    <Route element={<MainLayout />}>
                        <Route path="/" element={<Home />} />
                        <Route path="/folders" element={<Folders />} />
                        
                    </Route>
                </Route>
            </Routes>
        </BrowserRouter>
    );
};

export default router;