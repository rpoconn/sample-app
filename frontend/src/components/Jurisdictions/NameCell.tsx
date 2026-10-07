import type { ICellRendererParams } from "ag-grid-community"
import { ChevronDown, ChevronRight } from "lucide-react"

import { cn } from "@/lib/utils"
import type { JurisdictionGridContext, JurisdictionRow } from "./types"

export function NameCell({
    data,
    context,
}: ICellRendererParams<JurisdictionRow, unknown, JurisdictionGridContext>) {
    if (!data) return null
    const { jurisdiction: j, expanded } = data
    const Chevron = expanded ? ChevronDown : ChevronRight
    return (
        <div
            className="flex h-full items-center gap-1"
            style={{ paddingLeft: j.depth * 20 }}
        >
            {(j.child_count ?? 0) > 0 ? (
                <button
                    type="button"
                    aria-label={
                        expanded ? `Collapse ${j.name}` : `Expand ${j.name}`
                    }
                    className="rounded p-0.5 hover:bg-muted"
                    onClick={() => context.toggleExpanded(j.id)}
                >
                    <Chevron className="size-4" />
                </button>
            ) : (
                <span className="w-5" />
            )}
            <span
                className={cn(
                    j.is_structural && "font-semibold text-muted-foreground",
                )}
            >
                {j.name}
            </span>
        </div>
    )
}

export default NameCell
