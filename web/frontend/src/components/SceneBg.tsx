export function SceneBg() {
  return (
    <div className="lp-setup-bg" aria-hidden="true">
      {/* One focal point + CSS radar (::after) / drifting grid (::before) */}
      <svg className="lp-setup-bg-graph" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <circle className="lp-setup-bg-pulse" cx="980" cy="420" r="3.5" />
      </svg>
    </div>
  );
}
