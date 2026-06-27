import type { Metadata } from "next";
import { AuthProvider } from "@/hooks/useAuth";
import { ToastProvider } from "@/hooks/useToast";
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
      <body className="min-h-screen bg-[#FBFBFA] text-[#2F3437]">
        <AuthProvider>
          <ToastProvider>
            <Navbar />
            <main>{children}</main>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
