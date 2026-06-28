"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { PasswordInput } from "@/components/ui/PasswordInput";

export default function RegisterPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await api("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      router.push("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3rem)] px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-semibold text-[#2F3437] mb-2">Register</h1>
        <p className="text-sm text-gray-400 mb-8">Create your KnowledgeBase account</p>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50/50 p-3 text-sm text-red-600">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-xs font-medium text-gray-500 mb-1.5">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={2}
              maxLength={64}
              className="w-full rounded-lg border border-gray-200/60 bg-white px-4 py-2.5 text-sm text-[#2F3437] placeholder:text-gray-400 transition-all duration-150 focus:border-gray-400 focus:ring-0 focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-xs font-medium text-gray-500 mb-1.5">
              Password
            </label>
            <PasswordInput
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-[#1A1A1A] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#2F3437] disabled:opacity-40 transition-colors shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
          >
            {loading ? "Creating account…" : "Register"}
          </button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-400">
          Already have an account?{" "}
          <Link href="/login" className="text-[#2F3437] hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
