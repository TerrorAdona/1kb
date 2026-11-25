import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../../features/auth/authStore";

export function AuthGate({ children }: { children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const initialized = useAuthStore((state) => state.initialized);
  const location = useLocation();

  if (!initialized) {
    return (
      <div className="grid min-h-[55vh] place-items-center">
        <div className="loading-dot" aria-label="Chargement du compte" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return children;
}
