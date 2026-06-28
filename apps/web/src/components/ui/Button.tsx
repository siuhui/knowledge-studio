interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "secondary" | "danger" | "ghost";
  disabled?: boolean;
  className?: string;
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled = false,
  className = "",
}: ButtonProps) {
  const baseClass =
    "rounded-lg px-4 py-2 text-sm font-medium transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed";

  const variantClass = {
    primary: "bg-[#1A1A1A] text-white hover:bg-[#2F3437] shadow-[0_1px_3px_rgba(0,0,0,0.08)]",
    secondary:
      "border border-gray-200/60 text-[#2F3437] hover:bg-gray-100/70 hover:border-gray-300",
    danger: "border border-red-200 text-red-600 hover:bg-red-50 hover:border-red-300",
    ghost: "text-gray-500 hover:text-[#2F3437] hover:bg-gray-100/70",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${variantClass} ${className}`}
    >
      {children}
    </button>
  );
}
