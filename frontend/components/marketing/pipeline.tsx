import { Section } from "./section";

/**
 * The run, start to finish. Numbered because this genuinely is an ordered
 * pipeline — each step consumes the previous one's output — and the mono column
 * carries what actually happens at each stage rather than a marketing gloss.
 */
const STEPS = [
  {
    title: "You photograph it once",
    body: "A phone photo on a kitchen table is enough. The upload is hashed on arrival and stored as the authentic original.",
    tech: "SHA-256 · B2 object write",
  },
  {
    title: "The product gets read",
    body: "Shape, material, and colour are extracted so every later frame keeps the same object rather than inventing a new one.",
    tech: "Genblaze · vision pass",
  },
  {
    title: "The pack is generated",
    body: "Studio, lifestyle, on-model, and colour variants are produced step by step, with a short product video alongside. Each frame lands in the grid as it finishes.",
    tech: "gemini-3-pro-image-preview",
  },
  {
    title: "Provenance is bound in",
    body: "Each output is hashed and written with a manifest tying it to the original — content-bound, so re-encoding breaks the seal instead of hiding it.",
    tech: "XMP embed · content binding",
  },
  {
    title: "You export to the marketplace",
    body: "Amazon, Etsy, Shopify, eBay, and social presets come out correctly sized, with masters and manifests in the same archive.",
    tech: "ZIP · per-preset renditions",
  },
];

export function Pipeline() {
  return (
    <Section
      eyebrow="The run"
      title="Five steps, from photo to listing"
      description="An image-only pack takes a couple of minutes; adding the product video takes it to about five. Nothing here is a mock-up stage — each step writes real objects to Backblaze B2 and is visible in the job log while it happens."
    >
      <ol className="mt-10 grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-2 lg:grid-cols-5">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex flex-col gap-3 bg-card p-5">
            <div className="flex items-baseline gap-2.5">
              <span className="tabular font-mono text-xs text-accent">
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="h-px flex-1 bg-border" aria-hidden />
            </div>
            <h3 className="text-[15px] font-semibold tracking-tight">{s.title}</h3>
            <p className="flex-1 text-sm text-muted-foreground">{s.body}</p>
            {/* Wraps rather than truncates: a half-shown model id undercuts the
                precision this line exists to demonstrate. */}
            <p className="label-mono border-t pt-3 leading-relaxed text-muted-foreground/80 [overflow-wrap:anywhere]">
              {s.tech}
            </p>
          </li>
        ))}
      </ol>
    </Section>
  );
}
