import { ProvenanceBadge } from "@/components/provenance-badge";
import { Badge } from "@/components/ui/badge";

export function BadgeGallery() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Badge>Default</Badge>
      <Badge variant="secondary">Secondary</Badge>
      <Badge variant="outline">Outline</Badge>
      <Badge variant="warning">Warning</Badge>
      <ProvenanceBadge authentic sha="7f3a9c2e1b4d5a6f8c0e2d4b6a8c0e1f" />
      <ProvenanceBadge authentic={false} sha="a1b2c3d4e5f60718293a4b5c6d7e8f90" />
    </div>
  );
}
