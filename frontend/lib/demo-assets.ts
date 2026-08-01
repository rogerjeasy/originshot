// GENERATED — real OriginShot output pulled from Backblaze B2.
// Each `sha` is the true SHA-256 of the source asset in the bucket, and every
// one is checked against the live /verify API at sync time, so a hash shown on
// the marketing site always resolves. `model` and `provider` are read back from
// that same record — the site credits whoever actually served the run.
// Regenerate with scripts/sync-demo-assets.py.

export interface DemoAsset {
  slot: string;
  style: "studio" | "lifestyle" | "variant" | "onmodel" | "video";
  src: string;
  sha: string;
  /** Dimensions of the re-encoded copy served from /public — for layout. */
  width: number;
  height: number;
  /** Dimensions of the master in B2 — what the provenance record describes. */
  sourceWidth: number;
  sourceHeight: number;
  /** The model the stored provenance record names — never assumed. */
  model: string;
  /** The provider that actually served this frame. */
  provider: string;
}

export const DEMO_ASSETS: DemoAsset[] = [
  { slot: "lifestyle-01", style: "lifestyle", src: "/demo/lifestyle-01.webp", sha: "090cf9990f10209e53f40241115b20103be7a55fa266cb917901069dcdf6a0d9", width: 733, height: 1100, sourceWidth: 1024, sourceHeight: 1536, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "lifestyle-02", style: "lifestyle", src: "/demo/lifestyle-02.webp", sha: "0a1a5eea5fcc9265f767954587729f5587a0da68173174bd0f508500a2a8f8a6", width: 733, height: 1100, sourceWidth: 1024, sourceHeight: 1536, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "lifestyle-03", style: "lifestyle", src: "/demo/lifestyle-03.webp", sha: "2f522a727aec1461680639627b9201f92066ce159b96b6087c4d7041a3078a5f", width: 733, height: 1100, sourceWidth: 1024, sourceHeight: 1536, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "lifestyle-04", style: "lifestyle", src: "/demo/lifestyle-04.webp", sha: "850605e0a4713c5aaf8b527f3b6c97daae45bd25b3625a597d278c84da1f9902", width: 733, height: 1100, sourceWidth: 1024, sourceHeight: 1536, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "onmodel-01", style: "onmodel", src: "/demo/onmodel-01.webp", sha: "902b0b7df8966e4c7ae57eb883599fb46ef847264f9c4fc6f2bf3917ca96bf84", width: 733, height: 1100, sourceWidth: 1024, sourceHeight: 1536, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "studio-01", style: "studio", src: "/demo/studio-01.webp", sha: "11bfce586cc893088f4161379d2bc8f62f4752d7c9497bd2753b455c5b08de58", width: 1024, height: 1024, sourceWidth: 1024, sourceHeight: 1024, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "studio-02", style: "studio", src: "/demo/studio-02.webp", sha: "38d43fd1c6166d22a15c618f4e40fd12d96d5bfbe06e0e506c4be9db98e3b84c", width: 1024, height: 1024, sourceWidth: 1024, sourceHeight: 1024, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "studio-03", style: "studio", src: "/demo/studio-03.webp", sha: "42148eeb7c057391d9809db7036983f9c1da7b4858c6710907e24894cb76327d", width: 1024, height: 1024, sourceWidth: 1024, sourceHeight: 1024, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "variant-01", style: "variant", src: "/demo/variant-01.webp", sha: "2f17210180067cd711d17cc380fd10c52ed82a3602952a0fe05e9af7fbf83f36", width: 1024, height: 1024, sourceWidth: 1024, sourceHeight: 1024, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "variant-02", style: "variant", src: "/demo/variant-02.webp", sha: "4724a037780a19a972748d34ea849362cd9f513878f9698e70c38e47df4c4f4f", width: 1024, height: 1024, sourceWidth: 1024, sourceHeight: 1024, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "variant-03", style: "variant", src: "/demo/variant-03.webp", sha: "8208a42f515ced23d4a683bbd06436a2b73c6808921d130ce18ad4590206f5e0", width: 1024, height: 1024, sourceWidth: 1024, sourceHeight: 1024, model: "gpt-image-1", provider: "openai-dalle" },
  { slot: "video-01", style: "video", src: "/demo/video-6ae12d1e.mp4", sha: "6ae12d1e9969e45bc6ad62513c7d9e2323cf6007302d994d4f3a33ae3ae7b172", width: 960, height: 960, sourceWidth: 960, sourceHeight: 960, model: "Kling-Image2Video-V2.1-Master", provider: "gmicloud" },
];
