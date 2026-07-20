import { DEMO_ASSETS, type DemoAsset } from "./demo-assets";

/**
 * The demo pack, grouped by *where a seller puts the frame* rather than by which
 * pipeline style produced it. Those are two different taxonomies and conflating
 * them would be a lie on the page: "In context" below is not a sixth style, it
 * is more `lifestyle` output shown against a different question ("how big is
 * it?"). The pipeline's real five styles live in PACK_COMPOSITION.
 *
 * Shared by the landing gallery and /pack so the two can't drift.
 *
 * `variant-01` is deliberately absent. It is a bottle, not the demo mug, and
 * every surface here is built on the claim that one source photo produced all of
 * these — it would break that claim on sight.
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
    slots: ["studio-01", "studio-03", "studio-02", "studio-04"],
  },
  {
    id: "lifestyle",
    label: "Lifestyle",
    goes: "Etsy · Instagram",
    blurb: "The product in a room someone recognises. This is the frame that earns the click.",
    detail:
      "The frame that earns the click. A buyer scrolling a category page is deciding in about a second, and a mug on white loses that second to a mug on a windowsill. Same object, placed in a room the buyer already lives in.",
    slots: ["lifestyle-02", "lifestyle-05", "lifestyle-04", "lifestyle-01"],
  },
  {
    id: "scene",
    label: "In context",
    goes: "Listing gallery",
    blurb:
      "Desk, café and kitchen scenes, for the moment a buyer is working out how big the thing actually is.",
    detail:
      "Desk, café and kitchen scenes — these answer the question the returns process is made of: how big is it, really? Surrounding a product with objects of known size does more for scale than a dimensions table.",
    slots: ["scene-01", "scene-02", "lifestyle-03", "lifestyle-06"],
  },
  {
    id: "onmodel",
    label: "In hand",
    goes: "Scale · detail shot",
    blurb:
      "The product held, so a buyer can read its size instantly. A pack also sweeps colour and angle variants, which this demo mug only ships in one of.",
    detail:
      "The product held, so size reads instantly and without arithmetic. A full pack also sweeps colour and angle variants at this stage; the demo mug ships in a single finish, so there is nothing to sweep and only the in-hand frame came back.",
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
 */
export const PACK_COMPOSITION = [
  {
    style: "studio",
    outputs: 1,
    model: "gemini-3-pro-image-preview",
    use: "White-background frames that clear Amazon and eBay main-image rules.",
  },
  {
    style: "lifestyle",
    outputs: 2,
    model: "gemini-3-pro-image-preview",
    use: "The product in a room a buyer recognises — the frame that earns the click.",
  },
  {
    style: "on-model",
    outputs: 1,
    model: "gemini-3-pro-image-preview",
    use: "Held or worn, so scale reads instantly.",
  },
  {
    style: "variants",
    outputs: 2,
    model: "gemini-3-pro-image-preview",
    use: "Colour and angle sweeps, for products sold in more than one finish.",
  },
  {
    style: "video",
    outputs: 1,
    model: "Kling-Image2Video-V2.1-Master",
    use: "A five-second product video, generated from the studio frame.",
  },
];

/** Model credited per pipeline style, for the frame inspector. */
export function modelFor(style: DemoAsset["style"]): string {
  return style === "video" ? "Kling-Image2Video-V2.1-Master" : "gemini-3-pro-image-preview";
}
