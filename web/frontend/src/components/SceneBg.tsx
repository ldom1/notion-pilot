export function SceneBg() {
  return (
    <div className="lp-setup-bg" aria-hidden="true">
      <svg className="lp-setup-bg-graph" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <g className="lp-setup-bg-edges">
          <path d="M120 180H380L560 90H820" />
          <path d="M380 180V420H640L860 520" />
          <path d="M640 420V700H1100" />
          <path d="M820 90V300H1280" />
        </g>
        <g className="lp-setup-bg-dots">
          <circle cx="120" cy="180" r="3.5" />
          <circle cx="380" cy="180" r="3.5" />
          <circle cx="560" cy="90" r="3.5" />
          <circle cx="820" cy="90" r="3.5" />
          <circle cx="640" cy="420" r="3.5" />
          <circle cx="860" cy="520" r="3.5" />
          <circle className="lp-setup-bg-pulse" cx="1100" cy="700" r="3.5" />
          <circle className="lp-setup-bg-pulse" cx="1280" cy="300" r="3.5" />
        </g>
      </svg>
    </div>
  );
}
