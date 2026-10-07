import type { JurisdictionPublic, RegionType } from "@/client"
import type { JurisdictionFilters, StatusFilter, TypeFilters } from "./types"

type ById = Map<string, JurisdictionPublic>

export type FilterResult = {
    // Matches plus their ancestors, kept for context
    visible: Set<string>
    // Ancestors of matches, opened so every match is on screen
    expanded: Set<string>
    // Matching jurisdictions that can be opted into
    selectableCount: number
}

export type FacetOption = {
    id: string
    label: string
    // Nearest typed ancestor, to tell apart e.g. two cities named "Springfield"
    context?: string
    flagUrl?: string
}

export type Facet = {
    type: RegionType
    label: string
    options: FacetOption[]
    value: string[]
}

const typeLabels: Record<RegionType, string> = {
    country: "Country",
    subdivision: "State / Province",
    city: "City",
}

// Coarsest first: a finer facet only offers options under the coarser picks
const typeOrder: RegionType[] = ["country", "subdivision", "city"]

// Self first, then each ancestor up to the root
function chainOf(j: JurisdictionPublic, byId: ById) {
    const chain = [j]
    for (
        let a = j.parent_id ? byId.get(j.parent_id) : undefined;
        a;
        a = a.parent_id ? byId.get(a.parent_id) : undefined
    ) {
        chain.push(a)
    }
    return chain
}

function activeFacets(byType: TypeFilters) {
    return Object.values(byType)
        .filter((ids): ids is string[] => !!ids?.length)
        .map((ids) => new Set(ids))
}

export function isFiltering({ search, byType, status }: JurisdictionFilters) {
    return (
        search.trim() !== "" ||
        activeFacets(byType).length > 0 ||
        status !== "all"
    )
}

// Whether a row is on in the current scope (enabledIds). Available rows are off
// but licensed (licensedIds, the company's opt-ins), so they can be turned on.
// Structural rows can't be on or off; they show only as ancestors of matches.
function matchesStatus(
    j: JurisdictionPublic,
    status: StatusFilter,
    enabledIds: Set<string>,
    licensedIds: Set<string>,
) {
    if (status === "all") return true
    if (j.is_structural) return false
    const enabled = enabledIds.has(j.id)
    if (status === "enabled") return enabled
    if (status === "available") return !enabled && licensedIds.has(j.id)
    return !enabled
}

// Search and facets, everything but status. Across types filters combine with AND,
// within a type with OR. A row passes a type when it or an ancestor is picked, so
// picking a country keeps its whole subtree.
function matchesQuery(
    j: JurisdictionPublic,
    chain: JurisdictionPublic[],
    term: string,
    facets: Set<string>[],
) {
    if (!facets.every((ids) => chain.some((a) => ids.has(a.id)))) return false
    return (
        !term ||
        j.name.toLowerCase().includes(term) ||
        !!j.code?.toLowerCase().includes(term)
    )
}

export function filterTree(
    tree: JurisdictionPublic[],
    byId: ById,
    filters: JurisdictionFilters,
    enabledIds: Set<string>,
    licensedIds: Set<string>,
): FilterResult | null {
    if (!isFiltering(filters)) return null
    const term = filters.search.trim().toLowerCase()
    const facets = activeFacets(filters.byType)
    const visible = new Set<string>()
    const expanded = new Set<string>()
    let selectableCount = 0
    for (const j of tree) {
        if (!matchesStatus(j, filters.status, enabledIds, licensedIds)) continue
        const chain = chainOf(j, byId)
        if (!matchesQuery(j, chain, term, facets)) continue
        visible.add(j.id)
        if (!j.is_structural) selectableCount++
        for (const a of chain.slice(1)) {
            visible.add(a.id)
            expanded.add(a.id)
        }
    }
    return { visible, expanded, selectableCount }
}

// What each status tab would show under the current search and facets, counting
// only rows that can be on or off
export function statusCounts(
    tree: JurisdictionPublic[],
    byId: ById,
    filters: Pick<JurisdictionFilters, "search" | "byType">,
    enabledIds: Set<string>,
    licensedIds: Set<string>,
): Record<StatusFilter, number> {
    const term = filters.search.trim().toLowerCase()
    const facets = activeFacets(filters.byType)
    const counts = { all: 0, enabled: 0, available: 0, disabled: 0 }
    for (const j of tree) {
        if (j.is_structural) continue
        if (!matchesQuery(j, chainOf(j, byId), term, facets)) continue
        counts.all++
        if (enabledIds.has(j.id)) {
            counts.enabled++
        } else {
            counts.disabled++
            if (licensedIds.has(j.id)) counts.available++
        }
    }
    return counts
}

// One facet per region type present in the tree, each narrowed by the coarser picks
export function facetsFor(
    tree: JurisdictionPublic[],
    byId: ById,
    byType: TypeFilters,
    flagUrls: Map<string, string | undefined>,
): Facet[] {
    const present = new Set(tree.map((j) => j.region_type))
    const facets: Facet[] = []
    const coarser: Set<string>[] = []
    for (const type of typeOrder) {
        if (!present.has(type)) continue
        const options = tree
            .filter((j) => j.region_type === type)
            .map((j) => ({ j, chain: chainOf(j, byId) }))
            .filter(({ chain }) =>
                coarser.every((ids) => chain.some((a) => ids.has(a.id))),
            )
            .map(({ j, chain }) => ({
                id: j.id,
                label: j.name,
                context: chain.slice(1).find((a) => a.region_type)?.name,
                flagUrl: flagUrls.get(j.id),
            }))
            .sort((a, b) => a.label.localeCompare(b.label))
        // Picks orphaned by a coarser change drop out
        const allowed = new Set(options.map((o) => o.id))
        const value = (byType[type] ?? []).filter((id) => allowed.has(id))
        facets.push({ type, label: typeLabels[type], options, value })
        if (value.length) coarser.push(new Set(value))
    }
    return facets
}

// Applies a facet change and drops finer picks that fall outside the new selection
export function withFacet(
    tree: JurisdictionPublic[],
    byId: ById,
    byType: TypeFilters,
    type: RegionType,
    ids: string[],
): TypeFilters {
    const next = { ...byType, [type]: ids }
    return Object.fromEntries(
        facetsFor(tree, byId, next, new Map()).map((f) => [f.type, f.value]),
    )
}
