import Tooltip from "@mui/material/Tooltip"
import { Minus, Plus } from "lucide-react"
import type {
    JurisdictionGridContext,
    JurisdictionRow,
} from "@/components/jurisdictions/jurisdictionTypes"
import { LockedIcon } from "@/components/jurisdictions/renderers/LockedIcon"
import { Button } from "@/components/ui/Button"

// Turns everything under a row on or off at once, with how much of it is on.
// Sits beside the name in the tree; rows without children have nothing to select.
export function SelectAllControl({
    data,
    context,
}: {
    data: JurisdictionRow
    context: JurisdictionGridContext
}) {
    if (!data.subtree) return null
    const { jurisdiction: j, mode, disabled, subtree } = data
    const scope = mode === "company" ? "for the company" : "for me"
    // Everything the user is allowed to pick is on; a click then turns it off
    const allAvailable = subtree.total > 0 && subtree.enabled === subtree.total
    const locked = subtree.locked ?? 0
    // Fully on only when nothing is held back by the license
    const all = allAvailable && locked === 0
    const some = subtree.enabled > 0 && !all
    const grand = subtree.total + locked
    const lockedNote =
        locked > 0
            ? `${locked} of ${grand} in ${j.name} ${locked === 1 ? "isn't" : "aren't"} enabled for your company's license.`
            : ""
    return (
        <div className="flex items-center gap-1 text-xs">
            <Tooltip
                title={
                    subtree.total === 0 ? (
                        `Nothing in ${j.name} is enabled for your license`
                    ) : (
                        <span className="flex flex-col gap-1">
                            <span>
                                {allAvailable
                                    ? locked > 0
                                        ? `Everything available in ${j.name} is on. Click to turn it off.`
                                        : `Turn off everything in ${j.name}`
                                    : locked > 0
                                      ? `Turn on everything available in ${j.name}`
                                      : `Turn on everything in ${j.name}`}
                            </span>
                            {lockedNote && <span>{lockedNote}</span>}
                        </span>
                    )
                }
                placement="left"
                // The button says what it does; the tooltip is only for the details
                enterDelay={2000}
                enterNextDelay={2000}
                arrow
            >
                {/* A disabled button gets no pointer events, so the wrapper
                    carries the tooltip */}
                <span>
                    <Button
                        variant="ghost"
                        size="sm"
                        // A full-height hit area with a tinted hover, rather
                        // than just the text
                        className="h-7 gap-1 px-2 text-xs text-primary hover:bg-primary/10 hover:text-primary disabled:text-muted-foreground"
                        // Non-admins can't change company selections; nothing
                        // selectable means everything under the row is locked
                        disabled={
                            subtree.total === 0 ||
                            (mode === "company" && disabled)
                        }
                        aria-label={`Select all in ${j.name} ${scope} (${subtree.enabled} of ${grand} on)`}
                        aria-pressed={all ? true : some ? "mixed" : false}
                        // Turns off once everything available is on, even when
                        // the license holds some back
                        onClick={() =>
                            context.toggleSubtree(j.id, !allAvailable)
                        }
                    >
                        {allAvailable ? (
                            <Minus className="size-4" strokeWidth={2.5} />
                        ) : (
                            <Plus className="size-4" strokeWidth={2.5} />
                        )}
                        {allAvailable ? "Clear all" : "Select all"}
                    </Button>
                </span>
            </Tooltip>
            {/* A count only once something is on; "0 of n" is noise */}
            {subtree.enabled > 0 && (
                <span className="tabular-nums text-muted-foreground">
                    {subtree.enabled} of {grand}
                </span>
            )}
            {/* Nothing under the row can be enabled, so a count says nothing */}
            {subtree.total === 0 && <LockedIcon />}
        </div>
    )
}

export default SelectAllControl
