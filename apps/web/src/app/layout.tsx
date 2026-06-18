import type { Metadata } from "next";
import { AuthProvider } from "@/hooks/useAuth";
import { Navbar } from "@/components/layout/Navbar";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "KnowledgeBase",
  description: "Local knowledge retrieval and AI analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <AuthProvider>
          <Navbar />
          <main className="container mx-auto px-4 py-8 max-w-4xl">
            {children}
          </main>
        </AuthProvider>
      </body>
    </html>
  );
}
