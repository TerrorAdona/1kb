import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Menu, UserRound, X } from "lucide-react";
import { useAuthStore } from "../../features/auth/authStore";
import { Brand } from "./Brand";
import { buttonClass } from "./Button";

const links = [
  { to: "/lobby", label: "Multijoueur" },
  { to: "/solo", label: "Mode solo" },
];

export function AppShell() {
  const user = useAuthStore((state) => state.user);
  const initialized = useAuthStore((state) => state.initialized);
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="relative z-30 border-b border-forest/8 bg-paper/90 backdrop-blur-xl">
        <div className="mx-auto flex h-[76px] max-w-[1360px] items-center justify-between px-5 sm:px-8 lg:px-12">
          <Brand />
          <nav className="hidden items-center gap-1 md:flex" aria-label="Navigation principale">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                className={({ isActive }) =>
                  `rounded-full px-4 py-2.5 text-sm font-semibold transition ${
                    isActive ? "bg-forest/8 text-forest" : "text-stone-600 hover:text-forest"
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            {initialized && user ? (
              <Link to="/profile" className="profile-chip">
                <span className="grid size-9 place-items-center rounded-full bg-orange-100 text-orange-700">
                  {user.display_name.slice(0, 1).toUpperCase()}
                </span>
                <span className="max-w-32 truncate text-sm font-bold text-forest">
                  {user.display_name}
                </span>
              </Link>
            ) : (
              <>
                <Link to="/login" className="text-sm font-bold text-forest hover:text-orange-700">
                  Connexion
                </Link>
                <Link to="/register" className={buttonClass("secondary", "sm")}>
                  Créer un compte
                </Link>
              </>
            )}
          </div>
          <button
            type="button"
            className="grid size-11 place-items-center rounded-full border border-stone-200 text-forest md:hidden"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? "Fermer le menu" : "Ouvrir le menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
        {menuOpen && (
          <div className="absolute inset-x-0 top-full border-b border-stone-200 bg-paper p-4 shadow-xl md:hidden">
            <nav className="mx-auto flex max-w-3xl flex-col gap-1">
              <Link to="/lobby" onClick={() => setMenuOpen(false)} className="mobile-nav-link">
                Multijoueur
              </Link>
              <Link to="/solo" onClick={() => setMenuOpen(false)} className="mobile-nav-link">
                Mode solo
              </Link>
              {user ? (
                <Link to="/profile" onClick={() => setMenuOpen(false)} className="mobile-nav-link">
                  <UserRound size={17} /> Mon profil
                </Link>
              ) : (
                <div className="mt-2 grid grid-cols-2 gap-2">
                  <Link to="/login" onClick={() => setMenuOpen(false)} className={buttonClass("outline", "sm")}>
                    Connexion
                  </Link>
                  <Link to="/register" onClick={() => setMenuOpen(false)} className={buttonClass("secondary", "sm")}>
                    Inscription
                  </Link>
                </div>
              )}
            </nav>
          </div>
        )}
      </header>
      <main className="mx-auto min-h-[calc(100vh-76px)] max-w-[1440px] px-5 pb-16 pt-7 sm:px-8 lg:px-12">
        <Outlet />
      </main>
      <footer className="border-t border-forest/10 px-5 py-6 text-center text-xs text-stone-500">
        Un jeu inspiré du Mille Bornes classique · Prenez la route, à votre rythme.
      </footer>
    </div>
  );
}
