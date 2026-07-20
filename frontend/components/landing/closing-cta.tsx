import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Reveal } from "./section";

/**
 * The close. It repeats the hero's promise in one line and then gets out of the
 * way — the page has already shown its evidence, so this is a door, not another
 * pitch.
 */
export function ClosingCta() {
  return (
    <section className="band-ink viewing-light relative overflow-hidden">
      <div className="relative mx-auto max-w-[1320px] px-5 pb-24 pt-8 sm:px-8 sm:pb-32">
        <div className="kelvin-rule" aria-hidden />

        <Reveal>
          <div className="mt-16 flex flex-col items-start gap-10 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <h2 className="display-face text-[clamp(2.25rem,5.5vw,4rem)]">
                Your next listing is
                <br />
                one photo away.
              </h2>
              <p className="on-ink-mute mt-5 max-w-lg text-[16.5px] leading-relaxed">
                Start with a single product and a phone photo. You&apos;ll get the pack back in
                about five minutes, with a hash under every frame.
              </p>
            </div>

            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Link
                href="/studio"
                className="btn-tungsten inline-flex h-12 items-center justify-center gap-2 rounded-lg px-7 text-[15px] font-semibold"
              >
                Generate your first pack
                <ArrowRight className="size-4" />
              </Link>
              <Link
                href="/how-it-works"
                className="btn-on-ink inline-flex h-12 items-center justify-center rounded-lg px-7 text-[15px] font-medium"
              >
                How it works
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
