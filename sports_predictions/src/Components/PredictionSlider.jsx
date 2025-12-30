export default function PredictionSlider(props) {
  const away = props.away;
  const home = props.home;
  const linelength = props.linelength;
  const lineheight = props.lineheight;
  const dotSize = props.dotSize;
  const clamp = (v) => Math.max(0, Math.min(1, Number(v) || 0));
  const awayClamped = clamp(away);
  const homeClamped = clamp(home);

  //  calculate left position of the dot
  const leftFor = (pct) => {
    if (typeof linelength === "number") {
      return `${pct * linelength - dotSize / 2}px`;
    }
    return `calc(${pct * 100}% - ${dotSize / 2}px)`;
  };

  return (
    <div className="flex items-center">
      <div
        className="relative h-5 m-2"
        style={{
          width: linelength + "px",
          height: lineheight + "px",
        }}
      >
        <div className="absolute inset-0 bg-green-600 rounded" />
        <div
          aria-hidden
          className="absolute bg-green-600 rounded-full"
          style={{
            width: dotSize + "px",
            height: dotSize + "px",
            left: leftFor(awayClamped),
            top: "50%",
            transform: "translateY(-50%)",
          }}
        />
      </div>
    </div>
  );
}
