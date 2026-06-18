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
    <nav className="bg-white border-b border-gray-200">
      <div className="container mx-auto px-4 max-w-4xl flex items-center justify-between h-14">
        <Link href="/" className="font-bold text-lg text-gray-900">
          KnowledgeBase
        </Link>
        <div className="flex items-center gap-4">
          {isLoading ? null : user ? (
            <>
              <Link
                href="/knowledge-bases"
                className="text-sm text-gray-600 hover:text-gray-900"
              >
                Knowledge Bases
              </Link>
              <span className="text-sm text-gray-400">{user?.username}</span>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-500 hover:text-red-600 transition-colors"
              >
                Logout
              </button>
            </>
          ) : (
            <>
              <Link href="/login" className="text-sm text-gray-600 hover:text-gray-900">
                Sign In
              </Link>
              <Link
                href="/register"
                className="text-sm rounded-lg border px-3 py-1 text-gray-600 hover:bg-gray-100"
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
