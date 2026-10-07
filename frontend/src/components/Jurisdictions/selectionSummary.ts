import type { JurisdictionPublic } from "@/client"

export type SelectionEntry = {
    jurisdiction: JurisdictionPublic
    flagUrl?: string
    // Set when the whole subtree is on and is listed as one entry
    allOf?: number
}

export type SelectionGroup = {
    // Shared parent of the entries; undefined for top-level entries
    parent?: JurisdictionPublic
    entries: SelectionEntry[]
}

// Readable view of the selection: entries grouped under their parent, with any
// subtree that is fully on rolled up into its root ("California, all 12")
export function summarizeSelection(
    childrenOf: Map<string | null, JurisdictionPublic[]>,
    byId: Map<string, JurisdictionPublic>,
    flagUrls: Map<string, string | undefined>,
    enabledSet: Set<string>,
    isSelectable: (j: JurisdictionPublic) => boolean,
): SelectionGroup[] {
    const counts = new Map<string, { total: number; enabled: number }>()
    const count = (j: JurisdictionPublic) => {
        const self = isSelectable(j)
        const c = {
            total: self ? 1 : 0,
            enabled: self && enabledSet.has(j.id) ? 1 : 0,
        }
        for (const child of childrenOf.get(j.id) ?? []) {
            const s = count(child)
            c.total += s.total
            c.enabled += s.enabled
        }
        counts.set(j.id, c)
        return c
    }
    for (const root of childrenOf.get(null) ?? []) count(root)

    const groups = new Map<string | null, SelectionGroup>()
    const add = (j: JurisdictionPublic, allOf?: number) => {
        const key = j.parent_id ?? null
        let group = groups.get(key)
        if (!group) {
            group = { parent: key ? byId.get(key) : undefined, entries: [] }
            groups.set(key, group)
        }
        group.entries.push({
            jurisdiction: j,
            flagUrl: flagUrls.get(j.id),
            allOf,
        })
    }

    const walk = (parentId: string | null) => {
        for (const j of childrenOf.get(parentId) ?? []) {
            const c = counts.get(j.id)
            if (!c || c.enabled === 0) continue
            const hasChildren = (childrenOf.get(j.id)?.length ?? 0) > 0
            if (hasChildren && c.total > 1 && c.enabled === c.total) {
                add(j, c.total)
                continue
            }
            if (isSelectable(j) && enabledSet.has(j.id)) add(j)
            walk(j.id)
        }
    }
    walk(null)

    return [...groups.values()]
}
