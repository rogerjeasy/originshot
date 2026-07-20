import { Reveal, SectionHead } from "./section";

/**
 * What the app is actually built on, stated concretely enough to be checkable.
 *
 * Every line here is drawn from the code: keys come from app/storage.py
 * (`assets/<sha[:2]>/<sha[2:4]>/<sha><ext>`, private bucket, presigned GETs),
 * checkpoints from app/transparency.py, and the model IDs from
 * originshot_pipelines/registry.py — which lists only models this app really
 * calls. Nothing aspirational goes in this section; if it isn't wired, it isn't
 * here.
 */
const PILLARS = [
  {
    name: "Backblaze B2",
    role: "Every byte the product owns",
    rows: [
      ["Authentic originals", "hashed on arrival, stored as the anchor for the whole pack"],
      ["Masters + renditions", "one master per frame, resized per marketplace preset"],
      ["Provenance manifests", "the record each /verify lookup resolves against"],
      ["Ledger checkpoints", "the transparency log's published heads"],
    ],
    foot: "assets/<sha[:2]>/<sha[2:4]>/<sha><ext> — content-addressable, so identical bytes dedup on their own. Private bucket, short-lived presigned reads.",
  },
  {
    name: "Genblaze",
    role: "Every model call, in one shape",
    rows: [
      ["gemini-3-pro-image-preview", "source photo → studio, lifestyle, on-model, variants"],
      ["Kling-Image2Video-V2.1-Master", "studio frame → 5s product video, with i2v fallbacks"],
      ["x-ai/grok-4.5", "vision QA — catches a frame that drifted off the real product"],
      ["zai-org/GLM-5.1-FP8", "listing copy per sales channel"],
    ],
    foot: "One Pipeline API across providers: each step reports its real cost back, which is what the credit ledger debits — never an estimate dressed up as a bill.",
  },
];

export function Stack() {
  return (
    <section className="band-ink">
      <div className="mx-auto max-w-[1320px] px-5 py-20 sm:px-8 sm:py-28">
        <Reveal>
          <SectionHead
            tone="ink"
            kicker="Under the hood"
            title="Two dependencies, both load-bearing"
            lede="A generated image is only worth as much as the record behind it. That means storage that can prove what it holds, and an orchestration layer that reports what it actually did."
          />
        </Reveal>

        <Reveal delay={0.06}>
          <div className="mt-14 grid gap-6 lg:grid-cols-2 lg:gap-8">
            {PILLARS.map((p) => (
              <div
                key={p.name}
                className="flex min-w-0 flex-col overflow-hidden rounded-xl border"
                style={{ backgroundColor: "var(--ink-2)" }}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b px-6 py-5">
                  <h3 className="display-face text-[1.5rem]">{p.name}</h3>
                  <span className="kicker on-ink-mute">{p.role}</span>
                </div>

                <dl className="flex-1 divide-y">
                  {p.rows.map(([k, v]) => (
                    <div key={k} className="grid gap-1 px-6 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)] sm:gap-5">
                      <dt className="t-verify min-w-0 font-mono text-[12px] [overflow-wrap:anywhere]">
                        {k}
                      </dt>
                      <dd className="on-ink-mute min-w-0 text-[14px] leading-relaxed">{v}</dd>
                    </div>
                  ))}
                </dl>

                <p
                  className="on-ink-mute border-t px-6 py-4 text-[13px] leading-relaxed [overflow-wrap:anywhere]"
                  style={{ backgroundColor: "var(--ink-3)" }}
                >
                  {p.foot}
                </p>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
