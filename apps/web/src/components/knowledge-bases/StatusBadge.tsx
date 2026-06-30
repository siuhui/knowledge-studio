export const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-100 text-emerald-700",
  pending: "bg-amber-100 text-amber-700",
  invalid: "bg-red-100 text-red-600",
  processing: "bg-blue-100 text-blue-700",
  ready: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-600",
  running: "bg-blue-100 text-blue-700",
  done: "bg-emerald-100 text-emerald-700",
};

export function StatusBadge({ status }: { status: string }) {
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  const color = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-500";
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${color}`}>{label}</span>
  );
}
