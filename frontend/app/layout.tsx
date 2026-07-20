import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, Inter_Tight } from "next/font/google";

import { AuthProvider } from "@/components/auth-provider";
import { SessionProvider } from "@/lib/use-session";
import "./globals.css";

// Plex Mono carries everything machine-true — hashes, SKUs, models, dimensions.
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-mono",
});

// The two Light Table faces, now the whole product's type (Archivo was retired
// with the Calibration system). Bricolage has the width and weight to hold a
// full-bleed display line and is used for nothing else; Inter Tight sets every
// word a person actually reads, app and marketing alike.
const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-bricolage",
});

const interTight = Inter_Tight({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter-tight",
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
      className={`${plexMono.variable} ${bricolage.variable} ${interTight.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      {/* Browser extensions (Grammarly is the usual culprit) inject attributes
          like data-gr-ext-installed onto <body> before React hydrates, which
          React reports as a hydration mismatch. It is not ours to fix and there
          is nothing to patch up — the attributes are inert. The flag on <html>
          does not cover <body>'s own attributes, so it is needed on both. */}
      <body suppressHydrationWarning>
        {/* SessionProvider sits at the root, not in the (app) group, because
            /verify is public but renders the full AppShell for signed-in
            visitors — and AppShell reads the session. Mounting it here makes
            "a session is available anywhere you're authenticated" true
            everywhere, instead of leaving a trap for the next public page that
            shows app chrome. It no-ops when signed out: refresh() returns early
            with no fetches when there's no user. */}
        <AuthProvider>
          <SessionProvider>{children}</SessionProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
