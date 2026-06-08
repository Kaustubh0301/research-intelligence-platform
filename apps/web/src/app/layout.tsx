import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";
import { NavLinks } from "@/components/ui/NavLinks";

export const metadata: Metadata = {
  title: "Research Intelligence Platform",
  description: "ML paper corpus explorer",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          <div className="flex min-h-screen flex-col">
            <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
              <div className="container flex h-14 max-w-7xl mx-auto items-center px-4">
                <Link
                  href="/"
                  className="mr-6 flex items-center font-semibold text-sm"
                >
                  Research Intelligence
                </Link>
                <NavLinks />
              </div>
            </header>
            <main className="flex-1 container max-w-7xl mx-auto px-4 py-6">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
