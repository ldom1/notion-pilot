interface SpinnerProps {
  size?: number;
  fullPage?: boolean;
}

export function Spinner({ size = 32, fullPage = false }: SpinnerProps) {
  const borderWidth = size > 16 ? 3 : 2;
  const el = (
    <div
      className="spinner"
      style={{ width: size, height: size, borderWidth }}
      aria-label="Loading"
    />
  );
  if (fullPage) {
    return <div className="spinner-center">{el}</div>;
  }
  return el;
}
