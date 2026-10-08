import { ListChecks } from "lucide-react"
import type { JurisdictionMode } from "@/components/jurisdictions/jurisdictionTypes"
import type { SelectionEntry } from "@/components/jurisdictions/selection/selectionSummary"
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "@/components/ui/Sheet"

// The current selection as a flat, readable list of every jurisdiction that is on
export function SelectionSheet({
    open,
    onOpenChange,
    mode,
    entries,
    count,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    mode: JurisdictionMode
    // Undefined while the tree loads
    entries?: SelectionEntry[]
    count: number
}) {
    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="w-full sm:max-w-md">
                <SheetHeader className="pb-0">
                    <SheetTitle className="flex items-center gap-2">
                        <ListChecks className="size-5" />
                        {mode === "company"
                            ? "Company selection"
                            : "Your selection"}
                    </SheetTitle>
                    <SheetDescription>
                        {count === 0
                            ? "No jurisdictions are on."
                            : `${count} jurisdiction${count === 1 ? "" : "s"} on${mode === "company" ? " for this company" : ", monitored for you"}.`}
                    </SheetDescription>
                </SheetHeader>
                <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
                    {!entries ? (
                        <p className="py-8 text-center text-sm text-muted-foreground">
                            Loading…
                        </p>
                    ) : entries.length === 0 ? (
                        <p className="py-8 text-center text-sm text-muted-foreground">
                            Nothing selected yet. Turn on jurisdictions in the
                            table to see them here.
                        </p>
                    ) : (
                        <ul className="flex flex-col gap-2 py-2">
                            {entries.map(
                                ({ jurisdiction: j, flagUrl, parentPath }) => (
                                    <li
                                        key={j.id}
                                        className="flex items-center gap-2 text-sm"
                                    >
                                        {flagUrl ? (
                                            <img
                                                src={flagUrl}
                                                alt=""
                                                className="h-3.5 w-5 shrink-0 rounded-[2px] border object-cover"
                                            />
                                        ) : (
                                            <span className="w-5 shrink-0" />
                                        )}
                                        <span className="truncate">
                                            {j.name}
                                        </span>
                                        {j.code && (
                                            <span className="text-xs text-muted-foreground">
                                                {j.code}
                                            </span>
                                        )}
                                        {parentPath && (
                                            <span className="ml-auto truncate text-xs text-muted-foreground">
                                                {parentPath}
                                            </span>
                                        )}
                                    </li>
                                ),
                            )}
                        </ul>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    )
}

export default SelectionSheet
