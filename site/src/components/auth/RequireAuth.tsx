import { Navigate, Outlet } from "react-router";

export const RequireAuth = () => {
    const isAuthenticated = true

    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }

    return <Outlet />;
}