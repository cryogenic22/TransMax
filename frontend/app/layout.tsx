import type { Metadata } from "next";
import "./globals.css";
import "./landing.css";
import { AuthProvider } from "@/lib/auth";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "TransMax - Pharmaceutical Translation Platform",
  description: "AI-powered pharmaceutical translation with built-in quality assurance. Accurate translations for PIL, SPC, labels, and regulatory documents.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans bg-background text-foreground">
        <AuthProvider>
          {children}
          <Toaster position="top-right" richColors />
        </AuthProvider>
      </body>
    </html>
  );
}
