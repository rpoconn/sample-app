import type { JurisdictionPublic } from "@/client"
import { flagUrlFor } from "./flags"

export type SelectionEntry = {
    jurisdiction: JurisdictionPublic
    flagUrl?: string
    // Where it sits, to tell apart same-named entries ("Canada / Territories")
    parentPath?: string
}

// Every selected jurisdiction as a flat list, in the grid's top-down order
export function summarizeSelection(
    tree: JurisdictionPublic[],
    enabledSet: Set<string>,
    isSelectable: (j: JurisdictionPublic) => boolean,
): SelectionEntry[] {
    const byId = new Map(tree.map((j) => [j.id, j]))
    // Siblings keep the server's order
    const childrenOf = new Map<string | null, JurisdictionPublic[]>()
    for (const j of tree) {
        const key = j.parent_id ?? null
        childrenOf.set(key, [...(childrenOf.get(key) ?? []), j])
    }

    const entries: SelectionEntry[] = []
    const walk = (parentId: string | null) => {
        for (const j of childrenOf.get(parentId) ?? []) {
            if (enabledSet.has(j.id) && isSelectable(j)) {
                entries.push({
                    jurisdiction: j,
                    flagUrl: flagUrlFor(j, byId),
                    parentPath: j.parent_id
                        ? byId.get(j.parent_id)?.name_path
                        : undefined,
                })
            }
            walk(j.id)
        }
    }
    walk(null)
    return entries
}
