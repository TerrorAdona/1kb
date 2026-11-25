import { ArrowLeft, Mail } from "lucide-react";
import { Link } from "react-router-dom";
import { Notice } from "../../shared/components/Notice";

export function RecoveryPage() {
  return (
    <section className="mx-auto max-w-2xl py-10 sm:py-16">
      <Link to="/login" className="inline-flex items-center gap-2 text-sm font-bold text-forest hover:text-orange-700">
        <ArrowLeft size={16} /> Retour à la connexion
      </Link>
      <div className="mt-8 rounded-[2rem] border border-stone-200 bg-white p-7 shadow-card sm:p-10">
        <span className="grid size-12 place-items-center rounded-2xl bg-orange-100 text-orange-700">
          <Mail size={21} />
        </span>
        <p className="eyebrow mt-6">Récupération du compte</p>
        <h1 className="mt-2 font-display text-3xl font-black text-forest">Un oubli, ça arrive.</h1>
        <p className="mt-3 max-w-xl text-sm leading-6 text-stone-600">
          L’API actuelle ne propose pas encore de réinitialisation de mot de passe.
          Nous n’envoyons donc pas de faux e-mail de récupération.
        </p>
        <Notice tone="info">
          Contactez l’administrateur du jeu pour récupérer l’accès à votre compte.
        </Notice>
      </div>
    </section>
  );
}
