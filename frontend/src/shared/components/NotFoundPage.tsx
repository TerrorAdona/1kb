import { ButtonLink } from "./Button";

export function NotFoundPage() {
  return (
    <section className="mx-auto grid min-h-[60vh] max-w-xl place-items-center text-center">
      <div>
        <p className="eyebrow">Sortie manquée</p>
        <h1 className="mt-3 font-display text-4xl font-black text-forest">Cette route n’existe pas.</h1>
        <p className="mt-3 text-stone-600">Revenons sur une route plus familière.</p>
        <ButtonLink to="/" className="mt-7">Retour à l’accueil</ButtonLink>
      </div>
    </section>
  );
}
