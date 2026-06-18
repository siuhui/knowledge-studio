import Link from "next/link";

export default function Home() {
  return (
    <div className="text-center py-16">
      <h1 className="text-4xl font-bold text-gray-900 mb-4">KnowledgeBase</h1>
      <p className="text-lg text-gray-600 mb-8">
        Drop your documents in — search, ask, analyze with AI.
      </p>
      <div className="flex gap-4 justify-center">
        <Link
          href="/login"
          className="rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 transition-colors"
        >
          Sign In
        </Link>
        <Link
          href="/register"
          className="rounded-lg border border-gray-300 px-6 py-3 text-gray-700 font-medium hover:bg-gray-100 transition-colors"
        >
          Register
        </Link>
      </div>
    </div>
  );
}
