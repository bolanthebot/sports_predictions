import { Link } from "react-router-dom";

function SportCard({ title, subtitle, href }) {
  return (
    <Link
      to={href}
      className="panel group block rounded-xl border border-slate-700/70 p-6 transition-colors hover:border-orange-400/70"
    >
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-orange-300">
        {subtitle}
      </p>
      <h2 className="text-2xl font-bold text-slate-100 transition-colors group-hover:text-white">
        {title}
      </h2>
      <p className="mt-3 text-sm text-slate-400">Open {title} predictions</p>
    </Link>
  );
}

export default function SportLanding() {
  return (
    <section className="py-6 sm:py-8">
      <h1 className="mb-6 text-3xl font-bold text-slate-100 sm:text-4xl">Choose a Sport</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <SportCard title="NBA" subtitle="Basketball" href="/nba" />
        <SportCard title="MLB" subtitle="Baseball" href="/mlb" />
      </div>
    </section>
  );
}
