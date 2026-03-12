export default function KeyRow(props) {
  const { label, value } = props;

  return (
    <div className="flex gap-2 rounded-md border border-slate-700/60 bg-slate-800/35 px-2 py-1.5">
      <p className="text-slate-400">{label}:</p>
      <p className="font-medium text-slate-100">{String(value)}</p>
    </div>
  );
}
