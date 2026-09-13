export function Logo({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#1C1C1C" />
      <rect
        x="6.2"
        y="5.2"
        width="13.8"
        height="19.4"
        rx="2.4"
        stroke="#fff"
        strokeWidth="1.7"
      />
      <path
        d="M9.6 11.2h7.4M9.6 15.8h5.2M9.6 20.4h3.2"
        stroke="#fff"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <circle cx="22.2" cy="22.4" r="7.3" fill="#fff" />
      <path
        d="m19 22.5 2.2 2.3 4.6-5"
        stroke="#1C1C1C"
        strokeWidth="2.05"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
