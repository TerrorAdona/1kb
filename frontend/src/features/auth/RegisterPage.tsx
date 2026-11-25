import { useState, type FormEvent } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuthStore } from "./authStore";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";

export function RegisterPage() {
  const signUp = useAuthStore((state) => state.signUp);
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const [displayName, setDisplayName] = useState("");
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
      await signUp({ email, display_name: displayName, password });
      navigate("/", { replace: true });
    } catch (cause) {
      setError(apiErrorMessage(cause, "La création du compte a échoué."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="auth-layout">
      <div className="auth-art auth-art-register">
        <Link to="/" className="mb-auto text-sm font-bold text-cream/80 hover:text-white">← Retour à l’accueil</Link>
        <div className="relative z-10 max-w-md">
          <span className="auth-art-icon"><ShieldCheck size={20} /></span>
          <p className="mt-6 text-xs font-bold uppercase tracking-[.24em] text-orange-300">Votre prochaine aventure</p>
          <h1 className="mt-3 font-display text-4xl font-black leading-tight text-cream sm:text-5xl">
            Une route, mille histoires.
          </h1>
          <p className="mt-4 text-sm leading-7 text-cream/70">
            Créez votre profil et retrouvez vos parties depuis n’importe quel écran.
          </p>
        </div>
        <p className="relative z-10 mt-auto text-xs text-cream/45">Votre compte, vos parties, vos souvenirs.</p>
      </div>
      <div className="auth-form-wrap">
        <div className="mb-8">
          <p className="eyebrow">Première étape</p>
          <h2 className="mt-2 font-display text-3xl font-black text-forest">Créer un compte</h2>
          <p className="mt-2 text-sm text-stone-600">Quelques détails et vous êtes sur la ligne de départ.</p>
        </div>
        {error && <Notice tone="error">{error}</Notice>}
        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <label className="field-label">
            Nom de joueur
            <input
              className="form-input"
              type="text"
              autoComplete="nickname"
              maxLength={40}
              required
              value={displayName}
              onChange={(event) => setDisplayName(event.target.value)}
              placeholder="Comment vous appelle-t-on ?"
            />
          </label>
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
              autoComplete="new-password"
              minLength={8}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="8 caractères minimum"
            />
            <span className="mt-1 block text-xs font-normal text-stone-500">
              Le serveur vérifiera la robustesse de votre mot de passe.
            </span>
          </label>
          <Button type="submit" size="lg" loading={loading} className="mt-2 w-full">
            Créer mon compte <ArrowRight size={17} />
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-stone-600">
          Déjà un compte ?{" "}
          <Link to="/login" className="font-bold text-forest hover:text-orange-700">Se connecter</Link>
        </p>
      </div>
    </section>
  );
}
