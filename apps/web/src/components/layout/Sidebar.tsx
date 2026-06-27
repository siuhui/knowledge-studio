"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface SidebarProps {
  className?: string;
}

interface NavLink {
  href: string;
  label: string;
  active?: boolean;
  disabled?: boolean;
}

export function Sidebar({ className = "" }: SidebarProps) {
  const pathname = usePathname();

  const links: NavLink[] = [
    { href: "/knowledge-bases", label: "Knowledge Bases" },
    { href: "/knowledge-bases", label: "Upload", disabled: true },
    { href: "/knowledge-bases", label: "Search", disabled: true },
  ];

  return (
    <aside className={`w-56 shrink-0 px-3 py-4 ${className}`}>
      <nav className="space-y-0.5">
        {links.map((link) => {
          const isActive = pathname === link.href && !link.disabled;
          return link.disabled ? (
            <span
              key={link.label}
              className="block rounded-lg px-3 py-1.5 text-sm text-gray-300 cursor-default select-none"
            >
              {link.label}
            </span>
          ) : (
            <Link
              key={link.label}
              href={link.href}
              className={`block rounded-lg px-3 py-1.5 text-sm transition-colors ${
                isActive
                  ? "font-medium text-[#2F3437] bg-gray-100/70"
                  : "text-gray-500 hover:text-[#2F3437] hover:bg-gray-100/50"
              }`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
