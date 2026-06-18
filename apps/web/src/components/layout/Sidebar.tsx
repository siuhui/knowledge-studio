import Link from "next/link";

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className = "" }: SidebarProps) {
  return (
    <aside className={`w-56 border-r border-gray-200 p-4 ${className}`}>
      <nav className="space-y-1">
        <Link
          href="/knowledge-bases"
          className="block rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 transition-colors"
        >
          Knowledge Bases
        </Link>
        <Link
          href="/knowledge-bases"
          className="block rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-gray-100 transition-colors"
        >
          Upload
        </Link>
        <Link
          href="/knowledge-bases"
          className="block rounded-lg px-3 py-2 text-sm text-gray-500 hover:bg-gray-100 transition-colors"
        >
          Search
        </Link>
      </nav>
    </aside>
  );
}
