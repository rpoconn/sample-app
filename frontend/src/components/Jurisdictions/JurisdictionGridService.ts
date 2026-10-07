import { queryOptions } from "@tanstack/react-query"

import {
    CompaniesService,
    type CompanyAdmin,
    type CompanyPublic,
    type JurisdictionPublic,
    JurisdictionsService,
    type UserPublic,
    UsersService,
} from "@/client"
import type { FilterResult } from "./filterTree"
import type {
    JurisdictionMode,
    JurisdictionRow,
    JurisdictionSort,
    SubtreeSelection,
    Unlock,
} from "./types"

export type JurisdictionSummary = {
    total: number
    shown: number
    enabled: number
    locked?: number
}

export type BuildRowsInput = {
    tree: JurisdictionPublic[]
    childrenOf: Map<string | null, JurisdictionPublic[]>
    flagUrls: Map<string, string | undefined>
    filtered: FilterResult | null
    search: string
    expanded: Set<string>
    mode: JurisdictionMode
    company: CompanyPublic
    companyIds: string[]
    myIds: string[]
    canEditCompany: boolean
    showUserCounts: boolean
    userCounts?: Map<string, number>
    admins?: CompanyAdmin[]
    user: UserPublic
}

const idsOf = (res: { data: { data: JurisdictionPublic[] } }) =>
    res.data.data.map((j) => j.id)

// API access, cache keys and row building for the jurisdiction grid
// biome-ignore lint/complexity/noStaticOnlyClass: groups the grid's service logic in one place
export class JurisdictionGridService {
    static readonly defaultSort: JurisdictionSort = {
        sort_by: "name",
        sort_dir: "asc",
    }

    static readonly keys = {
        tree: (sort: JurisdictionSort, mode: JurisdictionMode) => [
            "jurisdictions",
            "tree",
            sort,
            // Only the enabled sort depends on which selections are shown
            sort.sort_by === "enabled" ? mode : null,
        ],
        company: (companyId: string) => ["company", companyId],
        companyIds: (companyId: string) => ["companyJurisdictions", companyId],
        myIds: ["myJurisdictions"],
        userCounts: (companyId: string) => [
            "companyJurisdictionUserCounts",
            companyId,
        ],
        admins: (companyId: string) => ["companyAdmins", companyId],
    }

    static treeQuery(sort: JurisdictionSort, mode: JurisdictionMode) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.tree(sort, mode),
            queryFn: async () =>
                (
                    await JurisdictionsService.readJurisdictionTree({
                        query: { ...sort, scope: mode },
                    })
                ).data.data,
        })
    }

    static companyQuery(companyId: string) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.company(companyId),
            queryFn: async () =>
                (
                    await CompaniesService.readCompany({
                        path: { company_id: companyId },
                    })
                ).data,
        })
    }

    static companyIdsQuery(companyId: string) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.companyIds(companyId),
            queryFn: async () =>
                idsOf(
                    await CompaniesService.readCompanyJurisdictions({
                        path: { company_id: companyId },
                    }),
                ),
        })
    }

    static myIdsQuery() {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.myIds,
            queryFn: async () =>
                idsOf(await UsersService.readMyJurisdictions()),
        })
    }

    static userCountsQuery(companyId: string) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.userCounts(companyId),
            queryFn: async () =>
                new Map(
                    (
                        await CompaniesService.readCompanyJurisdictionUserCounts(
                            { path: { company_id: companyId } },
                        )
                    ).data.data.map((c) => [c.jurisdiction_id, c.user_count]),
                ),
        })
    }

    static adminsQuery(companyId: string) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.admins(companyId),
            queryFn: async () =>
                (
                    await CompaniesService.readCompanyAdmins({
                        path: { company_id: companyId },
                    })
                ).data.data,
        })
    }

    static saveCompanyIds(companyId: string, ids: string[]) {
        return CompaniesService.setCompanyJurisdictions({
            path: { company_id: companyId },
            body: { jurisdiction_ids: ids },
        })
    }

    // Who would lose an opt-in if the company dropped these ids; always fresh
    static async affectedUsers(companyId: string, ids: string[]) {
        return (
            await CompaniesService.readCompanyJurisdictionAffectedUsers({
                path: { company_id: companyId },
                body: { jurisdiction_ids: ids },
            })
        ).data.data
    }

    static saveMyIds(ids: string[]) {
        return UsersService.setMyJurisdictions({
            body: { jurisdiction_ids: ids },
        })
    }

    static nextIds(current: string[], ids: string[], enabled: boolean) {
        if (enabled) return [...new Set([...current, ...ids])]
        const drop = new Set(ids)
        return current.filter((x) => !drop.has(x))
    }

    // Whether a row can be switched on in this scope. Users can only pick what the
    // company has opted into.
    static isSelectable(
        j: JurisdictionPublic,
        mode: JurisdictionMode,
        companySet: Set<string>,
    ) {
        return !j.is_structural && (mode === "company" || companySet.has(j.id))
    }

    // The jurisdiction and all its descendants
    static subtreeOf(
        childrenOf: Map<string | null, JurisdictionPublic[]>,
        root: JurisdictionPublic,
    ) {
        const out: JurisdictionPublic[] = []
        const stack = [root]
        for (let j = stack.pop(); j; j = stack.pop()) {
            out.push(j)
            stack.push(...(childrenOf.get(j.id) ?? []))
        }
        return out
    }

    // Asks the company's admins to turn a jurisdiction on, linking to where they'd do it
    static requestUnlock(
        admins: CompanyAdmin[],
        jurisdiction: string,
        company: string,
        user: UserPublic,
    ): Unlock | undefined {
        if (admins.length === 0) return undefined
        const to = admins
            .map((a) => encodeURIComponent(a.email).replace("%40", "@"))
            .join(",")
        const subject = `Please enable ${jurisdiction} for ${company}`
        const body = [
            "Hi,",
            "",
            `Could you turn on ${jurisdiction} for ${company}? It has to be enabled company-wide before I can select it.`,
            "",
            `You can turn it on here: ${window.location.origin}/company-admin`,
            "",
            "Thanks,",
            user.full_name || user.email,
        ].join("\n")
        const [only] = admins
        return {
            kind: "email",
            href: `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`,
            label:
                admins.length === 1
                    ? `Email ${only.full_name || only.email} to request it`
                    : "Email your company admins to request it",
        }
    }

    // Siblings keep the server's order, which reflects the current sort
    static childrenOf(tree: JurisdictionPublic[]) {
        const map = new Map<string | null, JurisdictionPublic[]>()
        for (const j of tree) {
            const key = j.parent_id ?? null
            map.set(key, [...(map.get(key) ?? []), j])
        }
        return map
    }

    // Flattens the visible, expanded part of the tree into grid rows
    static buildRows({
        tree,
        childrenOf,
        flagUrls,
        filtered,
        search,
        expanded,
        mode,
        company,
        companyIds,
        myIds,
        canEditCompany,
        showUserCounts,
        userCounts,
        admins,
        user,
    }: BuildRowsInput): {
        rows: JurisdictionRow[]
        summary: JurisdictionSummary
    } {
        const companySet = new Set(companyIds)
        const mySet = new Set(myIds)
        const highlight = filtered ? search.trim() || undefined : undefined
        const lockedReason = "Not enabled for your license."
        const enabledSet = mode === "company" ? companySet : mySet

        // Select-all state per parent, counted over the whole tree so filters
        // and collapsed rows don't change what "all" means
        const subtrees = new Map<string, SubtreeSelection>()
        const count = (j: JurisdictionPublic): SubtreeSelection => {
            const self = JurisdictionGridService.isSelectable(
                j,
                mode,
                companySet,
            )
            const sel = {
                total: self ? 1 : 0,
                enabled: self && enabledSet.has(j.id) ? 1 : 0,
                locked: !self && !j.is_structural ? 1 : 0,
            }
            const children = childrenOf.get(j.id) ?? []
            for (const c of children) {
                const s = count(c)
                sel.total += s.total
                sel.enabled += s.enabled
                sel.locked += s.locked
            }
            if (children.length > 0) subtrees.set(j.id, sel)
            return sel
        }
        for (const root of childrenOf.get(null) ?? []) count(root)

        const result: JurisdictionRow[] = []
        const walk = (parentId: string | null) => {
            for (const j of childrenOf.get(parentId) ?? []) {
                if (filtered && !filtered.visible.has(j.id)) continue
                const isExpanded = expanded.has(j.id)
                const base = {
                    jurisdiction: j,
                    mode,
                    flagUrl: flagUrls.get(j.id),
                    expanded: isExpanded,
                    highlight,
                    subtree: subtrees.get(j.id),
                }
                if (mode === "company") {
                    result.push({
                        ...base,
                        checked: companySet.has(j.id),
                        disabled: !canEditCompany,
                        disabledReason: canEditCompany
                            ? undefined
                            : "Only company admins can change this",
                        locked: false,
                        userCount: showUserCounts
                            ? (userCounts?.get(j.id) ?? 0)
                            : undefined,
                    })
                } else {
                    const allowed = companySet.has(j.id)
                    const locked = !allowed && !j.is_structural
                    result.push({
                        ...base,
                        checked: mySet.has(j.id),
                        disabled: !allowed,
                        disabledReason: allowed ? undefined : lockedReason,
                        locked,
                        unlock: !locked
                            ? undefined
                            : canEditCompany
                              ? { kind: "company" }
                              : JurisdictionGridService.requestUnlock(
                                    admins ?? [],
                                    j.name,
                                    company.name,
                                    user,
                                ),
                    })
                }
                if (isExpanded) walk(j.id)
            }
        }
        walk(null)

        const selectable = tree.filter((j) => !j.is_structural)
        return {
            rows: result,
            summary: {
                total: selectable.length,
                shown: filtered?.selectableCount ?? selectable.length,
                enabled: (mode === "company" ? companyIds : myIds).length,
                locked:
                    mode === "user"
                        ? selectable.filter((j) => !companySet.has(j.id)).length
                        : undefined,
            },
        }
    }
}
