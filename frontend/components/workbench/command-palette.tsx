"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import { CornerDownLeft, Search } from "lucide-react";

import { cn } from "@/lib/utils";

export type Command = {
  id: string;
  label: string;
  /** The region this command belongs to — mirrors the sidebar's grouping. */
  group: string;
  href: string;
  keywords?: string;
  icon?: React.ComponentType<{ className?: string }>;
};

/**
 * ⌘K navigation.
 *
 * Hand-rolled rather than pulling in cmdk: the whole behaviour is a filtered
 * list with roving selection, and this app's dependency surface is part of what
 * it asks people to trust.
 *
 * Matching is substring over label + keywords, not fuzzy. Fuzzy matching is
 * flashier and worse here — with ~10 destinations it mostly produces confident
 * wrong answers, and a seller looking for "Catalog" should not be shown
 * "Analytics" because the letters happen to appear in order.
 */
export function CommandPalette({ commands }: { commands: Command[] }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const router = useRouter();
  const listRef = useRef<HTMLDivElement>(null);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) =>
      `${c.label} ${c.group} ${c.keywords ?? ""}`.toLowerCase().includes(q),
    );
  }, [commands, query]);

  const groups = useMemo(() => {
    const out: { name: string; items: Command[] }[] = [];
    for (const c of results) {
      const g = out.find((x) => x.name === c.group);
      if (g) g.items.push(c);
      else out.push({ name: c.group, items: [c] });
    }
    return out;
  }, [results]);

  // Grouping reorders: results [A(g1), B(g2), C(g1)] renders as A, C, B. The
  // keyboard must walk what the eye sees, so selection indexes this flattened
  // view and never `results` — otherwise Enter opens a different row than the
  // one highlighted, and only for users whose filter happens to interleave.
  const ordered = useMemo(() => groups.flatMap((g) => g.items), [groups]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Reset per opening, not per keystroke, so the selection survives typing.
  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
    }
  }, [open]);

  // Clamp rather than reset: narrowing the list shouldn't throw the user back
  // to the top, but the index must never point past the end.
  useEffect(() => {
    setActive((i) => Math.min(i, Math.max(0, ordered.length - 1)));
  }, [ordered.length]);

  const run = useCallback(
    (c: Command | undefined) => {
      if (!c) return;
      setOpen(false);
      router.push(c.href);
    },
    [router],
  );

  function onInputKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % Math.max(1, ordered.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i - 1 + ordered.length) % Math.max(1, ordered.length));
    } else if (e.key === "Enter") {
      e.preventDefault();
      run(ordered[active]);
    }
  }

  useEffect(() => {
    listRef.current
      ?.querySelector('[data-active="true"]')
      ?.scrollIntoView({ block: "nearest" });
  }, [active]);

  let flat = -1;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group flex h-9 items-center gap-2 rounded-md border bg-card ps-2.5 pe-2 text-sm text-muted-foreground transition-colors hover:bg-secondary"
        aria-label="Search and jump to a screen"
      >
        <Search className="size-4" />
        <span className="hidden sm:inline">Jump to…</span>
        <kbd className="label-mono ms-2 hidden rounded border bg-background px-1.5 py-0.5 text-muted-foreground sm:inline">
          ⌘K
        </kbd>
      </button>

      <Dialog.Root open={open} onOpenChange={setOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="anim-overlay fixed inset-0 z-50 bg-foreground/25 backdrop-blur-[2px]" />
          <Dialog.Content
            className="anim-pop fixed left-1/2 top-[18%] z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-0 overflow-hidden rounded-xl border bg-popover shadow-float"
            aria-label="Command palette"
          >
            <Dialog.Title className="sr-only">Jump to a screen</Dialog.Title>

            <div className="flex items-center gap-2.5 border-b px-4">
              <Search aria-hidden className="size-4 shrink-0 text-muted-foreground" />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={onInputKey}
                placeholder="Search screens…"
                aria-label="Search screens"
                className="h-12 w-full bg-transparent text-[0.9375rem] outline-none placeholder:text-muted-foreground"
              />
            </div>

            <div ref={listRef} className="scroll-thin max-h-[min(24rem,50vh)] overflow-y-auto p-2">
              {results.length === 0 ? (
                <p className="px-3 py-8 text-center text-sm text-muted-foreground">
                  No screen matches “{query}”.
                </p>
              ) : (
                groups.map((g) => (
                  <div key={g.name} className="mb-1 last:mb-0">
                    <p className="label px-3 pb-1 pt-2 text-muted-foreground/70">{g.name}</p>
                    {g.items.map((c) => {
                      flat += 1;
                      const i = flat;
                      const Icon = c.icon;
                      return (
                        <button
                          key={c.id}
                          type="button"
                          data-active={i === active}
                          onMouseMove={() => setActive(i)}
                          onClick={() => run(c)}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-md px-3 py-2 text-start text-sm transition-colors",
                            i === active
                              ? "bg-secondary text-foreground"
                              : "text-muted-foreground",
                          )}
                        >
                          {Icon && <Icon className="size-4 shrink-0" />}
                          <span className="min-w-0 flex-1 truncate text-foreground">
                            {c.label}
                          </span>
                          {i === active && (
                            <CornerDownLeft aria-hidden className="size-3.5 shrink-0" />
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
