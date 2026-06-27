"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

export function Navbar() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  return (
    <nav className="sticky top-0 z-40 bg-[#FBFBFA]/80 backdrop-blur-sm border-b border-gray-200/60">
      <div className="flex items-center justify-between h-12 px-6">
        <Link
          href="/"
          className="font-semibold text-sm tracking-tight text-[#1A1A1A]"
        >
          KnowledgeBase
        </Link>
        <div className="flex items-center gap-4">
          {isLoading ? null : user ? (
            <button
              type="button"
              onClick={handleLogout}
              className="text-xs text-gray-400 hover:text-red-500 transition-colors"
            >
              Logout
            </button>
          ) : (
            <>
              <Link
                href="/login"
                className="text-xs text-gray-500 hover:text-[#2F3437] transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/register"
                className="text-xs rounded-lg border border-gray-200/60 px-3 py-1 text-gray-500 hover:text-[#2F3437] hover:bg-gray-100/70 transition-all"
              >
                Register
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
