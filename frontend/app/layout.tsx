import type { Metadata } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";

import { AuthProvider } from "@/components/auth-provider";
import "./globals.css";

// Archivo carries the interface: a grotesk drawn for print and screen
// performance, set tight and heavy for headlines, wide and tracked for labels.
const archivo = Archivo({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-archivo",
});

// Plex Mono carries everything machine-true — hashes, SKUs, models, dimensions.
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "OriginShot — one photo to a full product catalog",
  description:
    "Turn one phone photo into studio shots, lifestyle scenes, variants, and a product video — each with verifiable provenance. Generated with Genblaze, stored on Backblaze B2.",
};

// Set the theme class before paint to avoid a flash.
const themeScript = `(function(){try{var s=localStorage.getItem('theme');var d=s?s==='dark':matchMedia('(prefers-color-scheme: dark)').matches;if(d)document.documentElement.classList.add('dark');}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${archivo.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
