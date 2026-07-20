"use client";

import { Plus } from "lucide-react";

/**
 * Answers are written against the code, not the pitch. Earlier versions of this
 * list claimed providers that aren't wired (OpenAI, Luma, Imagen/Veo) and models
 * that aren't used (Seedream, FLUX, Seedance). If the registry or the pricing
 * table changes, these change with them.
 *
 * Native <details> rather than a JS accordion: it is open-by-default for search
 * engines and reader modes, keyboard-operable for free, and needs no library.
 */
const FAQ = [
  {
    q: "Do I need a real product shoot?",
    a: "No. One ordinary phone photo is enough. OriginShot treats it as the authentic source and builds the rest of the catalog around it.",
  },
  {
    q: "What does “provenance-verified” actually mean?",
    a: "Every generated file carries an embedded, content-bound SHA-256 manifest. Drop the file on the Verify page and we re-hash the bytes and re-read the manifest — showing whether it's an authentic original, an AI generation, or has been altered since it left us.",
  },
  {
    q: "Which models does it actually use?",
    a: "Images — studio, lifestyle, on-model and variants — all run on gemini-3-pro-image-preview, orchestrated by Genblaze through GMI Cloud. Video runs on Kling-Image2Video-V2.1-Master, falling back to pixverse-v5.6-i2v and then wan2.6-r2v. The model that produced a given file is recorded in its manifest, so you never have to take this page's word for it.",
  },
  {
    q: "What happens to the photo I upload?",
    a: "It's validated, re-encoded to strip EXIF and GPS, hashed, and stored as your authentic original. Files you drop on the Verify page are different — those are read in memory to check them and never persisted.",
  },
  {
    q: "Where are my assets stored?",
    a: "On Backblaze B2 — durable, S3-compatible object storage, isolated per account. The bucket is private and reads are short-lived presigned URLs. Storage is content-addressable, so identical bytes are stored exactly once.",
  },
  {
    q: "Can I use these images on Amazon and Etsy?",
    a: "That's what the presets are for — each marketplace preset sizes the master to that platform's requirements, and studio frames are built to clear main-image rules. Disclosure requirements are yours to meet, and the manifest gives you something concrete to disclose with.",
  },
  {
    q: "What if the result isn't good enough?",
    a: "Regenerate the style you're unhappy with rather than the whole pack — you're only charged for what runs. Every frame stays in your library with its own record, so nothing is overwritten.",
  },
];

export function Faq() {
  return (
    <div className="mt-12 max-w-3xl">
      {FAQ.map(({ q, a }) => (
        <details key={q} className="group border-t">
          <summary className="flex cursor-pointer list-none items-start justify-between gap-6 py-5 text-[16.5px] font-medium tracking-[-0.015em] [&::-webkit-details-marker]:hidden">
            {q}
            <Plus className="on-paper-mute mt-1 size-4 shrink-0 transition-transform duration-200 group-open:rotate-45" />
          </summary>
          <p className="on-paper-mute max-w-prose pb-6 text-[15px] leading-relaxed">{a}</p>
        </details>
      ))}
    </div>
  );
}
