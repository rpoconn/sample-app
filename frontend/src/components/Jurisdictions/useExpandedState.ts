import { useState } from "react"

import type { JurisdictionPublic } from "@/client"
import type { FilterResult } from "./filterTree"

// Browsing and filtering keep separate expansion: a filter opens the ancestors of
// its matches, and clearing it returns to what the user had open before
export function useExpandedState(
    tree: JurisdictionPublic[],
    filtered: FilterResult | null,
) {
    const [expanded, setExpanded] = useState<Set<string>>(
        () => new Set(tree.filter((j) => j.parent_id == null).map((j) => j.id)),
    )
    const [filterView, setFilterView] = useState({
        result: filtered,
        expanded: new Set(filtered?.expanded),
    })
    if (filterView.result !== filtered) {
        setFilterView({
            result: filtered,
            expanded: new Set(filtered?.expanded),
        })
    }
    const shownExpanded = filtered ? filterView.expanded : expanded
    const updateExpanded = (update: (prev: Set<string>) => Set<string>) =>
        filtered
            ? setFilterView((v) => ({ ...v, expanded: update(v.expanded) }))
            : setExpanded(update)

    return { expanded: shownExpanded, updateExpanded }
}

export default useExpandedState
