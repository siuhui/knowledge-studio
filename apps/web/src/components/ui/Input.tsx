interface InputProps {
  type?: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  className?: string;
}

export function Input({
  type = "text",
  value,
  onChange,
  placeholder,
  required = false,
  className = "",
}: InputProps) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      required={required}
      className={`w-full rounded-lg border border-gray-200/60 bg-white px-4 py-2.5 text-sm text-[#2F3437] placeholder:text-gray-400 transition-all duration-150 focus:border-gray-400 focus:ring-0 focus:outline-none ${className}`}
    />
  );
}
