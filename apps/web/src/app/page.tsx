"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/hooks/useAuth";

export default function Home() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/knowledge-bases");
    }
  }, [isLoading, user, router]);

  if (isLoading || user) return null;

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3rem)] px-4 text-center">
      <h1 className="text-4xl font-semibold tracking-tight text-[#2F3437] mb-3">KnowledgeBase</h1>
      <p className="text-base text-gray-400 max-w-md mb-10">
        Drop your documents in — search, ask, analyze with AI.
      </p>
      <div className="flex gap-3">
        <Link
          href="/login"
          className="rounded-lg bg-[#1A1A1A] px-6 py-2.5 text-sm font-medium text-white hover:bg-[#2F3437] transition-colors shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
        >
          Sign in
        </Link>
        <Link
          href="/register"
          className="rounded-lg border border-gray-200/60 px-6 py-2.5 text-sm font-medium text-[#2F3437] hover:bg-gray-100/70 transition-all"
        >
          Register
        </Link>
      </div>
    </div>
  );
}
