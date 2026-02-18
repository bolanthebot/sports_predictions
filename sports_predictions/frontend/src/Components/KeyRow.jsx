export default function KeyRow(props) {
  const { label, value } = props;

  return (
    <div className="flex gap-2">
      <p className=" text-slate-300">{label}:</p>
      <p className="text-slate-100">{String(value)}</p>
    </div>
  );
}
