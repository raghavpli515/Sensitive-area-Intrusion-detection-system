export function ConfidenceSlider({
  value,
  onChange,
  disabled = false,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  return (
    <label className="confidence-slider">
      <span>Confidence threshold: {value.toFixed(2)}</span>
      <input
        type="range"
        min={0.1}
        max={0.9}
        step={0.05}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
