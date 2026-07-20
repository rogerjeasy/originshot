import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";

import { DEMO_ASSETS } from "@/lib/demo-assets";
import { Reveal } from "@/components/landing/section";

/**
 * The page's centrepiece: one real run, entered as a ledger.
 *
 * The alternative — an abstract five-box diagram — asks the reader to trust a
 * drawing. This walks the actual job that produced the frames on the home page,
 * so each stage can carry its true artifact: the key the object is written
 * under, the model that ran, the cost the provider billed. A seller reads it as
 * "here is what happens to my photo"; anyone auditing reads it as a job record.
 *
 * Every figure is derived: the per-style table is `pricing.breakdown()`
 * (`_OUTPUTS`, `_UNIT`, `_ETA_SECONDS`), the key format is `storage.storage_key`,
 * the models are `originshot_pipelines/registry.py`.
 */

const GENERATE_ROWS = [
  ["studio", "1", "0:25", "$0.04"],
  ["lifestyle", "2", "0:45", "$0.08"],
  ["on-model", "1", "0:30", "$0.04"],
  ["variants", "2", "0:45", "$0.08"],
  ["video", "1", "2:30", "$0.50"],
];

const STAGES = [
  {
    title: "Your photo arrives",
    body: "A phone photo is enough. Before anything is stored it's checked for what it claims to be, re-encoded to strip EXIF and GPS, and hashed. That hash is the anchor every later frame points back to.",
    machine: [
      ["check", "magic-byte type · pixel cap · bomb guard"],
      ["strip", "re-encode to PNG · no EXIF, no GPS"],
      ["write", "assets/<sha[:2]>/<sha[2:4]>/<sha>.png"],
    ],
  },
  {
    title: "The product gets read",
    body: "One vision pass extracts shape, material and colour. Every later frame is generated against that reading rather than against the previous frame — which is why the object stays the same object instead of drifting shot to shot.",
    machine: [
      ["run", "Genblaze · vision pass"],
      ["carry", "original passed to every step as reference"],
    ],
  },
  {
    title: "The pack is generated",
    body: "Five styles, run one after another. Each finished frame is hashed and written to B2 as it lands, so the job log fills in while you watch rather than going quiet for five minutes.",
    machine: [
      ["image", "gemini-3-pro-image-preview"],
      ["video", "Kling-Image2Video-V2.1-Master"],
    ],
    table: true,
  },
  {
    title: "Provenance is bound in",
    body: "Each output is written with a manifest naming the model that made it, the original it came from, and the disclosure. The manifest lives in the file's own bytes, so re-encoding the image breaks the seal instead of quietly surviving it. The hash is then appended to the transparency log.",
    machine: [
      ["embed", "XMP manifest · content-bound to the pixels"],
      ["append", "hash chain · checkpointed to B2 every 10 entries"],
    ],
    sample: true,
  },
  {
    title: "You export to the marketplace",
    body: "Presets for Amazon, Etsy, Shopify, eBay and social come out correctly sized. Masters and manifests travel in the same archive, so the proof doesn't get separated from the picture.",
    machine: [
      ["build", "per-preset renditions from the master"],
      ["ship", "ZIP · images + manifests"],
    ],
  },
];

export function RunLedger() {
  const sample = DEMO_ASSETS.find((a) => a.slot === "studio-01") ?? DEMO_ASSETS[0];

  return (
    <ol className="mt-16 flex flex-col">
      {STAGES.map((s, i) => (
        <li key={s.title}>
          <Reveal>
            {/* The spine: index rail, prose, machine column. It only becomes a
                three-column record at lg — below that the rail would eat the
                width the prose needs. */}
            <div className="grid gap-x-8 gap-y-6 border-t py-10 lg:grid-cols-[3.5rem_minmax(0,1fr)_minmax(0,26rem)] lg:py-14">
              {/* Index only. An earlier pass ran a vertical spine down this rail
                  as well, but the full-width rule between entries already does
                  that work — two separators for one relationship is one too
                  many. */}
              <span className="kicker t-accent tabular">{String(i + 1).padStart(2, "0")}</span>

              <div className="min-w-0">
                <h3 className="text-[1.375rem] font-semibold tracking-[-0.025em]">{s.title}</h3>
                <p className="on-paper-mute mt-3 max-w-prose text-[15.5px] leading-relaxed">
                  {s.body}
                </p>

                {s.table && (
                  <div
                    className="mt-7 overflow-hidden rounded-lg border"
                    style={{ backgroundColor: "var(--paper-2)" }}
                  >
                    <table className="w-full text-left">
                      <caption className="kicker on-paper-mute border-b px-4 py-2.5 text-left">
                        What a full pack costs to run
                      </caption>
                      <thead>
                        <tr className="kicker on-paper-mute">
                          <th scope="col" className="px-4 py-2.5 font-medium">
                            style
                          </th>
                          <th scope="col" className="px-4 py-2.5 text-right font-medium">
                            files
                          </th>
                          <th scope="col" className="px-4 py-2.5 text-right font-medium">
                            time
                          </th>
                          <th scope="col" className="px-4 py-2.5 text-right font-medium">
                            est.
                          </th>
                        </tr>
                      </thead>
                      <tbody className="font-mono text-[12.5px]">
                        {GENERATE_ROWS.map(([style, files, time, cost]) => (
                          <tr key={style} className="border-t">
                            <td className="px-4 py-2.5">{style}</td>
                            <td className="tabular px-4 py-2.5 text-right">{files}</td>
                            <td className="tabular on-paper-mute px-4 py-2.5 text-right">{time}</td>
                            <td className="tabular px-4 py-2.5 text-right">{cost}</td>
                          </tr>
                        ))}
                        <tr className="border-t font-semibold" style={{ backgroundColor: "var(--paper)" }}>
                          <td className="px-4 py-3">total</td>
                          <td className="tabular px-4 py-3 text-right">7</td>
                          <td className="tabular px-4 py-3 text-right">4:55</td>
                          <td className="tabular px-4 py-3 text-right">$0.74</td>
                        </tr>
                      </tbody>
                    </table>
                    <p className="on-paper-mute border-t px-4 py-3 text-[13px] leading-relaxed">
                      An estimate from list prices, quoted as a ceiling. You&apos;re debited what
                      the provider actually bills — if a run comes in under, the difference is
                      refunded rather than kept.
                    </p>
                  </div>
                )}
              </div>

              {/* The machine column: what a log would record for this stage. */}
              <div className="min-w-0 lg:pt-1">
                <dl className="grid gap-3">
                  {s.machine.map(([k, v]) => (
                    <div key={k} className="grid grid-cols-[4.25rem_minmax(0,1fr)] gap-3">
                      <dt className="kicker t-verify pt-0.5">{k}</dt>
                      <dd className="min-w-0 font-mono text-[12.5px] leading-relaxed [overflow-wrap:anywhere]">
                        {v}
                      </dd>
                    </div>
                  ))}
                </dl>

                {s.sample && (
                  <figure
                    className="mt-6 overflow-hidden rounded-lg border"
                    style={{ backgroundColor: "var(--paper-2)" }}
                  >
                    <figcaption className="flex items-center justify-between gap-2 border-b px-3.5 py-2.5">
                      <span className="kicker on-paper-mute">A real record</span>
                      <span className="kicker t-verify inline-flex items-center gap-1.5">
                        <ShieldCheck className="size-3.5" />
                        Verified
                      </span>
                    </figcaption>
                    <dl className="divide-y font-mono text-[11.5px]">
                      {[
                        ["sha256", `${sample.sha.slice(0, 24)}…`],
                        ["model", "gemini-3-pro-image-preview"],
                        ["content_bound", "true"],
                        ["disclosure", "AI-generated"],
                      ].map(([k, v]) => (
                        <div key={k} className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2 px-3.5 py-2.5">
                          <dt className="on-paper-mute truncate">{k}</dt>
                          <dd className="min-w-0 truncate">{v}</dd>
                        </div>
                      ))}
                    </dl>
                    <div className="border-t p-2.5">
                      <Link
                        href={`/verify/${sample.sha}`}
                        className="inline-flex items-center gap-1.5 text-[13px] font-medium underline decoration-1 underline-offset-4"
                      >
                        Check this hash yourself
                        <ArrowRight className="size-3.5" />
                      </Link>
                    </div>
                  </figure>
                )}
              </div>
            </div>
          </Reveal>
        </li>
      ))}
    </ol>
  );
}
