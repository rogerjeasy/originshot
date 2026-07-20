import { Reveal, SectionHead } from "./section";

/**
 * The run, start to finish.
 *
 * Numbered because this genuinely is an ordered pipeline — each step consumes
 * the previous step's output — so the index carries real information rather
 * than decorating the layout. The mono line under each step names what actually
 * executes, taken from originshot_pipelines/registry.py.
 */
const STEPS = [
  {
    title: "You photograph it once",
    body: "A phone photo on a kitchen table is enough. The upload is hashed on arrival and stored as the authentic original.",
    tech: "SHA-256 · B2 object write",
  },
  {
    title: "The product gets read",
    body: "Shape, material and colour are extracted so every later frame keeps the same object instead of inventing a new one.",
    tech: "Genblaze · vision pass",
  },
  {
    title: "The pack is generated",
    body: "Studio, lifestyle, on-model and colour variants are produced step by step, with a product video alongside. Each frame lands in the grid as it finishes.",
    tech: "gemini-3-pro-image-preview",
  },
  {
    title: "Provenance is bound in",
    body: "Each output is hashed and written with a manifest tying it to the original — content-bound, so re-encoding breaks the seal instead of hiding it.",
    tech: "XMP embed · content binding",
  },
  {
    title: "You export to the marketplace",
    body: "Amazon, Etsy, Shopify, eBay and social presets come out correctly sized, with masters and manifests in the same archive.",
    tech: "ZIP · per-preset renditions",
  },
];

export function RunSequence() {
  return (
    <section className="band-ink viewing-light relative overflow-hidden">
      <div className="relative mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
        <Reveal>
          <SectionHead
            tone="ink"
            kicker="The run"
            title="Five steps, photo to listing"
            lede="An image-only pack takes about two minutes; adding the product video takes it to five. No step here is a mock-up — each one writes real objects to Backblaze B2 and is visible in the job log while it happens."
          />
        </Reveal>

        <Reveal delay={0.06}>
          <ol className="mt-14 grid gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-5 lg:gap-x-8">
            {STEPS.map((s, i) => (
              <li key={s.title} className="relative flex min-w-0 flex-col">
                {/* The sequence rail: a hairline with a tungsten node at each
                    exposure. On mobile the steps stack, so the rail goes away
                    rather than being redrawn vertically at half strength. */}
                <div className="flex items-center gap-3" aria-hidden>
                  <span
                    className="size-1.5 shrink-0 rounded-full"
                    style={{ backgroundColor: "var(--tungsten)" }}
                  />
                  <span className="h-px flex-1" style={{ backgroundColor: "var(--ink-line)" }} />
                </div>

                <span className="kicker on-ink-mute mt-5 tabular">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h3 className="mt-3 text-[17px] font-semibold tracking-[-0.02em]">{s.title}</h3>
                <p className="on-ink-mute mt-2.5 flex-1 text-[14.5px] leading-relaxed">{s.body}</p>
                <p
                  className="t-verify mt-5 border-t pt-3 font-mono text-[11px] leading-relaxed [overflow-wrap:anywhere]"
                >
                  {s.tech}
                </p>
              </li>
            ))}
          </ol>
        </Reveal>
      </div>
    </section>
  );
}
