import type { ICellRendererParams } from "ag-grid-community"
import { ChevronDown, ChevronRight } from "lucide-react"
import type {
    JurisdictionGridContext,
    JurisdictionRow,
} from "@/components/jurisdictions/jurisdictionTypes"
import { LockedIcon } from "@/components/jurisdictions/renderers/LockedIcon"
import { cn } from "@/lib/utils"

// Splits text around the first case-insensitive match of term
function splitMatch(text: string, term?: string) {
    const at = term ? text.toLowerCase().indexOf(term.toLowerCase()) : -1
    if (!term || at < 0) return null
    return [
        text.slice(0, at),
        text.slice(at, at + term.length),
        text.slice(at + term.length),
    ]
}

export function NameCell({
    data,
    context,
}: ICellRendererParams<JurisdictionRow, unknown, JurisdictionGridContext>) {
    if (!data) return null
    const {
        jurisdiction: j,
        depth,
        flagUrl,
        expanded,
        hasChildren,
        locked,
        highlight,
    } = data
    const Chevron = expanded ? ChevronDown : ChevronRight
    const nameParts = splitMatch(j.name, highlight)
    const codeParts = j.code ? splitMatch(j.code, highlight) : null
    return (
        <div
            className="flex h-full items-center gap-1"
            style={{ paddingLeft: depth * 20 }}
        >
            {hasChildren ? (
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
            {flagUrl ? (
                <img
                    src={flagUrl}
                    alt=""
                    className="mx-1 h-3.5 w-5 shrink-0 rounded-[2px] border object-cover"
                />
            ) : (
                <span className="mx-1 w-5 shrink-0" />
            )}
            {/* Structural names sit between normal and locked text: a dark grey,
                while locked names are muted and further faded by the row */}
            <span
                className={cn(
                    j.is_structural && "font-semibold text-foreground/70",
                    locked && "text-muted-foreground",
                )}
            >
                {nameParts ? (
                    <>
                        {nameParts[0]}
                        <mark className="rounded-sm bg-yellow-200 px-0.5 text-inherit dark:bg-yellow-500/40">
                            {nameParts[1]}
                        </mark>
                        {nameParts[2]}
                    </>
                ) : (
                    j.name
                )}
            </span>
            {j.code && (
                <span className="text-xs text-muted-foreground">
                    ·{" "}
                    {codeParts ? (
                        <>
                            {codeParts[0]}
                            <mark className="rounded-sm bg-yellow-200 px-0.5 text-inherit dark:bg-yellow-500/40">
                                {codeParts[1]}
                            </mark>
                            {codeParts[2]}
                        </>
                    ) : (
                        j.code
                    )}
                </span>
            )}
            {locked && <LockedIcon className="ml-1" />}
        </div>
    )
}

export default NameCell
