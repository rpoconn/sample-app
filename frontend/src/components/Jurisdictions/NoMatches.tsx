import { CircleCheck, SearchX } from "lucide-react"

import { Button } from "@/components/ui/button"

// Shown over the grid body when filters hide every row. An empty Available tab
// is good news, not a failed search.
export function NoMatches({
    allTaken,
    onClear,
}: {
    // Available is empty under no other filter: every licensed row is on
    allTaken: boolean
    onClear: () => void
}) {
    const Icon = allTaken ? CircleCheck : SearchX
    return (
        <div className="absolute inset-x-0 top-12 bottom-0 flex flex-col items-center justify-center gap-2 text-center">
            <Icon className="size-8 text-muted-foreground" />
            <p className="font-medium">
                {allTaken
                    ? "You've enabled everything your company licenses"
                    : "No jurisdictions match your filters"}
            </p>
            <Button variant="outline" size="sm" onClick={onClear}>
                Clear filters
            </Button>
        </div>
    )
}

export default NoMatches
