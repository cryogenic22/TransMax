import type { Metadata } from "next";
import "./globals.css";
import "./landing.css";
import { AuthProvider } from "@/lib/auth";
import { Toaster } from "sonner";

export const metadata: Metadata = {
  title: "TransMax — Auditable AI translation for regulated pharma",
  description:
    "Multi-agent translation with cryptographic audit, deterministic quality gates, and signed evidence bundles. Built for PIL, SmPC, IFU, and the rest of the regulator-facing label.",
  icons: {
    icon: [
      { url: "/transmax-mark.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "32x32" },
    ],
  },
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
