// GENERATED — real OriginShot output pulled from Backblaze B2.
// Each `sha` is the true SHA-256 of the source asset in the bucket, so any
// hash shown on the marketing site resolves against /verify.
// Regenerate with scripts/sync-demo-assets.py.

export interface DemoAsset {
  slot: string;
  style: "studio" | "lifestyle" | "variant" | "onmodel" | "video";
  src: string;
  sha: string;
  width: number;
  height: number;
}

export const DEMO_ASSETS: DemoAsset[] = [
  // The hero video, copied from B2 rather than re-encoded: its bytes still carry
  // the embedded manifest, so `provenance.verify_file()` on this exact file
  // returns present + verified + content_bound. Do not re-compress it — that
  // breaks the content binding and the hash below stops matching.
  { slot: "video-01", style: "video", src: "/demo/video-6ae12d1e.mp4", sha: "6ae12d1e9969e45bc6ad62513c7d9e2323cf6007302d994d4f3a33ae3ae7b172", width: 960, height: 960 },
  { slot: "lifestyle-01", style: "lifestyle", src: "/demo/lifestyle-01.webp", sha: "028ac16c44cdc6bd0244de422c66e809111c39a5dc4de96b0ddebcbe95ef91f7", width: 886, height: 1100 },
  { slot: "studio-01", style: "studio", src: "/demo/studio-01.webp", sha: "16612e919d2df83603f44fb08f9878257f91d66135d75a9f265bf2ad01cf183c", width: 1024, height: 1024 },
  { slot: "lifestyle-02", style: "lifestyle", src: "/demo/lifestyle-02.webp", sha: "2ff8fde1741295a3ffc625120233f53bbd2f223f966734c46ad7f20a6c7c7c36", width: 886, height: 1100 },
  { slot: "variant-01", style: "variant", src: "/demo/variant-01.webp", sha: "3a1656bddbc7fe7f182a2e8c0c56e1705e0af325a373ab6609159bbfc9d9ab4f", width: 1024, height: 1024 },
  { slot: "lifestyle-03", style: "lifestyle", src: "/demo/lifestyle-03.webp", sha: "404466499eafc6ee0e8d53812cce8d5cee0283591e8bcd75cba240a0f26d566d", width: 886, height: 1100 },
  { slot: "onmodel-01", style: "onmodel", src: "/demo/onmodel-01.webp", sha: "4b2b705dbcddfc7fe2530944ff7ea4009e36562a822b649ab14faa6da19eadaf", width: 261, height: 357 },
  { slot: "lifestyle-04", style: "lifestyle", src: "/demo/lifestyle-04.webp", sha: "6bf689dac2b1f67b89e95557b8697bebe30f3e798994607344a0d5f5e9b54ae5", width: 886, height: 1100 },
  { slot: "scene-01", style: "lifestyle", src: "/demo/scene-01.webp", sha: "7b30afcc6f4aa44282dc4751b6bd0208666f2afa7999219aa3f29018e5008df1", width: 886, height: 1100 },
  { slot: "studio-02", style: "studio", src: "/demo/studio-02.webp", sha: "7d32f691df2a6f63ac27aff9fbac125af152274d918c1927f7110ef241b7a772", width: 1024, height: 1024 },
  { slot: "scene-02", style: "lifestyle", src: "/demo/scene-02.webp", sha: "bece137e8c83132fd79143328f87f484454c6ccf06ffd80074d1b077b8e7e7a7", width: 886, height: 1100 },
  { slot: "studio-03", style: "studio", src: "/demo/studio-03.webp", sha: "cec2a305ad34f1bbcf53214c3cfc6602082e23c83f607d9d7347fb4e7df24499", width: 1024, height: 1024 },
  { slot: "lifestyle-05", style: "lifestyle", src: "/demo/lifestyle-05.webp", sha: "edd6a2a0dc9f2b41fa4df7a310ad677fb19e7daed36bcf4cb45f29dfeefcd00c", width: 886, height: 1100 },
  { slot: "lifestyle-06", style: "lifestyle", src: "/demo/lifestyle-06.webp", sha: "f2c0bdfa31da3cc021e77ef5c35af46c788daa2f2e2f5490c74ce97371396ebf", width: 886, height: 1100 },
  { slot: "studio-04", style: "studio", src: "/demo/studio-04.webp", sha: "fa99236f85bac6f6cac92082702d15a3494fc297d83235320835ab6ca665951b", width: 1024, height: 1024 },
];
