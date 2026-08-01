import { DEMO_ASSETS, type DemoAsset } from "./demo-assets";

/**
 * The demo pack, grouped by *where a seller puts the frame* rather than by which
 * pipeline style produced it. Those are two different taxonomies and conflating
 * them would be a lie on the page: "In context" below is not a separate style, it
 * is more `lifestyle` output shown against a different question ("how big is
 * it?"). The pipeline's real five styles live in PACK_COMPOSITION.
 *
 * Shared by the landing gallery and /pack so the two can't drift.
 *
 * Every slot referenced here is a still from ONE source photograph (the anchored
 * original 05993b99f9af) and every one is manifest-embedded, content-bound and
 * present in the transparency log — which is what lets these pages invite you to
 * check any frame rather than asking you to take the gallery's word for it. The
 * hero video is the single exception to the shared-original claim: it derives
 * from a second photograph of the same mug, so copy scopes "one source photo" to
 * the stills and credits the video separately.
 */
export interface PackGroup {
  id: string;
  label: string;
  /** Where the frame is destined to be used. */
  goes: string;
  /** One line, for the landing gallery. */
  blurb: string;
  /** The longer read, for /pack. */
  detail: string;
  slots: string[];
}

export const PACK_GROUPS: PackGroup[] = [
  {
    id: "studio",
    label: "Studio",
    goes: "Amazon · eBay main image",
    blurb:
      "Clean white-background shots that clear marketplace main-image rules, with no lightbox and no tripod.",
    detail:
      "Amazon and eBay both reject a main image that isn't on pure white with the product filling most of the frame. These clear that bar without a lightbox, a sweep or a tripod — the model is given the source photo as a reference and asked to relight it, not to invent a new object.",
    slots: ["studio-01", "studio-02", "studio-03"],
  },
  {
    id: "lifestyle",
    label: "Lifestyle",
    goes: "Etsy · Instagram",
    blurb: "The product in a room someone recognises. This is the frame that earns the click.",
    detail:
      "The frame that earns the click. A buyer scrolling a category page is deciding in about a second, and a mug on white loses that second to a mug on a café table. Same object, placed in a room the buyer already lives in.",
    slots: ["lifestyle-02", "lifestyle-03"],
  },
  {
    id: "scene",
    label: "In context",
    goes: "Listing gallery",
    blurb:
      "Desk and shelf scenes, for the moment a buyer is working out how big the thing actually is.",
    detail:
      "Desk and shelf scenes — these answer the question the returns process is made of: how big is it, really? Surrounding a product with objects of known size (a laptop, a folded towel) does more for scale than a dimensions table.",
    slots: ["lifestyle-01", "lifestyle-04"],
  },
  {
    id: "variant",
    label: "Colour",
    goes: "Variant listings",
    blurb:
      "The same mug swept through the finishes it sells in — one photo covering every colourway.",
    detail:
      "A seller who lists one product in three glazes needs three sets of photographs, and normally shoots three times. These are the same mug — same form, same handle, same proportions — restaged into each finish from the single original, which is the case where generating rather than shooting saves the most money.",
    slots: ["variant-01", "variant-02", "variant-03"],
  },
  {
    id: "onmodel",
    label: "In hand",
    goes: "Scale · detail shot",
    blurb: "The product held, so a buyer can read its size instantly.",
    detail:
      "The product held, so size reads instantly and without arithmetic. It is also the frame that is hardest to fake convincingly, which is why it is QA-scored against the original like every other style rather than being waved through.",
    slots: ["onmodel-01"],
  },
  {
    id: "motion",
    label: "Video",
    goes: "Search · social",
    blurb:
      "A five-second product video made from the studio frame — the asset marketplaces now push hardest in search.",
    detail:
      "Five seconds of motion, generated from the studio frame rather than from the original photo — video models hold an object far better when they start from a clean, evenly lit plate. This is the asset marketplaces currently push hardest in search ranking, and the one almost no small seller has.",
    slots: ["video-01"],
  },
];

/** Resolve a group's slots to real assets, dropping any the sync script hasn't produced. */
export function framesFor(group: PackGroup): DemoAsset[] {
  return group.slots
    .map((slot) => DEMO_ASSETS.find((a) => a.slot === slot))
    .filter((a): a is DemoAsset => Boolean(a));
}

/** Every frame on the sheet, in group order. */
export function allFrames(): { asset: DemoAsset; group: PackGroup }[] {
  return PACK_GROUPS.flatMap((group) => framesFor(group).map((asset) => ({ asset, group })));
}

/**
 * What one pack actually contains — mirrors `_OUTPUTS` in backend/app/pricing.py.
 * Keep the counts in step with that table; the totals on this page are derived
 * from them.
 *
 * `model` is the pipeline's *configured primary*, from
 * backend/originshot_pipelines/registry.py. It is deliberately not the model
 * credited on any individual frame: the sheet on this page was served by the
 * cross-provider fallback while GMI's image queue was out of credit, and each
 * frame reports whichever provider actually answered. Showing the configured
 * model here and the real one there is the honest pairing — collapsing them
 * either way would misstate something.
 */
export const PACK_COMPOSITION = [
  {
    style: "studio",
    outputs: 1,
    model: "gemini-3-pro-image-preview",
    fallback: "gpt-image-1",
    use: "White-background frames that clear Amazon and eBay main-image rules.",
  },
  {
    style: "lifestyle",
    outputs: 2,
    model: "gemini-3-pro-image-preview",
    fallback: "gpt-image-1",
    use: "The product in a room a buyer recognises — the frame that earns the click.",
  },
  {
    style: "on-model",
    outputs: 1,
    model: "gemini-3-pro-image-preview",
    fallback: "gpt-image-1",
    use: "Held or worn, so scale reads instantly.",
  },
  {
    style: "variants",
    outputs: 2,
    model: "gemini-3-pro-image-preview",
    fallback: "gpt-image-1",
    use: "Colour and angle sweeps, for products sold in more than one finish.",
  },
  {
    style: "video",
    outputs: 1,
    model: "Kling-Image2Video-V2.1-Master",
    fallback: "pixverse-v5.6-i2v",
    use: "A five-second product video, generated from the studio frame.",
  },
];

/**
 * Human-readable provider name for a record's provider id.
 *
 * The ids come from the registry (`openai-dalle` is the SDK's name for the
 * gpt-image endpoint, not a claim that DALL·E made the picture), so they are
 * translated for display rather than printed raw.
 */
export function providerLabel(provider: string): string {
  if (provider.startsWith("openai")) return "OpenAI";
  if (provider.startsWith("gmi")) return "GMI Cloud";
  return provider;
}

/** The model credited on a frame — read from its stored record, never assumed. */
export function modelFor(asset: DemoAsset): string {
  return asset.model;
}
