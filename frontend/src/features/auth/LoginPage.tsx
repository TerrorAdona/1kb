import { useState, type FormEvent } from "react";
import { ArrowLeft, ArrowRight, KeyRound } from "lucide-react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "./authStore";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";

export function LoginPage() {
  const signIn = useAuthStore((state) => state.signIn);
  const user = useAuthStore((state) => state.user);
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await signIn(email, password);
      navigate((location.state as { from?: string } | null)?.from ?? "/", { replace: true });
    } catch (cause) {
      setError(apiErrorMessage(cause, "Connexion impossible. Vérifiez vos identifiants."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="auth-layout">
      <div className="auth-art auth-art-login">
        <Link to="/" className="mb-auto inline-flex items-center gap-2 text-sm font-bold text-cream/80 hover:text-white">
          <ArrowLeft size={16} /> Retour à l’accueil
        </Link>
        <div className="relative z-10 max-w-md">
          <span className="auth-art-icon"><KeyRound size={20} /></span>
          <p className="mt-6 text-xs font-bold uppercase tracking-[.24em] text-orange-300">La route vous attend</p>
          <h1 className="mt-3 font-display text-4xl font-black leading-tight text-cream sm:text-5xl">
            Reprenez votre place au volant.
          </h1>
          <p className="mt-4 text-sm leading-7 text-cream/70">
            Retrouvez vos parties, vos amis et vos kilomètres parcourus.
          </p>
        </div>
        <p className="relative z-10 mt-auto text-xs text-cream/45">Mille Bornes · Édition en ligne</p>
      </div>
      <div className="auth-form-wrap">
        <div className="mb-9">
          <p className="eyebrow">Content de vous revoir</p>
          <h2 className="mt-2 font-display text-3xl font-black text-forest">Connexion</h2>
          <p className="mt-2 text-sm text-stone-600">Entrez vos identifiants pour reprendre la route.</p>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
          <label className="field-label">
            Adresse e-mail
            <input
              className="form-input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="vous@exemple.fr"
            />
          </label>
          <label className="field-label">
            Mot de passe
            <input
              className="form-input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Votre mot de passe"
            />
          </label>
          <div className="flex justify-end">
            <Link to="/recover" className="text-sm font-semibold text-orange-700 hover:text-orange-800">
              Mot de passe oublié ?
            </Link>
          </div>
          <Button type="submit" size="lg" loading={loading} className="w-full">
            Se connecter <ArrowRight size={17} />
          </Button>
        </form>
        <p className="mt-7 text-center text-sm text-stone-600">
          Nouveau sur la route ?{" "}
          <Link to="/register" className="font-bold text-forest hover:text-orange-700">Créer un compte</Link>
        </p>
      </div>
    </section>
  );
}
