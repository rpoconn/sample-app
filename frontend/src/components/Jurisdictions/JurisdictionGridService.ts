import { queryOptions } from "@tanstack/react-query"

import {
    type JurisdictionFilters as ApiFilters,
    CompaniesService,
    type CompanyAdmin,
    type CompanyPublic,
    type JurisdictionGridRow,
    type JurisdictionRowsQuery,
    JurisdictionsService,
    type UserPublic,
    UsersService,
} from "@/client"
import { flagUrlForKeys } from "./flags"
import type {
    JurisdictionFilters,
    JurisdictionMode,
    JurisdictionRow,
    JurisdictionSort,
    TypeFilters,
    Unlock,
} from "./types"

// What a server row's grid state depends on beyond the row itself
export type RowInputs = {
    mode: JurisdictionMode
    company: CompanyPublic
    user: UserPublic
    canEditCompany: boolean
    admins?: CompanyAdmin[]
}

const idsOf = (res: { data: { data: { id: string }[] } }) =>
    res.data.data.map((j) => j.id)

const pickedTypes = (byType: TypeFilters) =>
    Object.entries(byType).filter(([, ids]) => ids?.length)

// API access, cache keys and row mapping for the jurisdiction grid
// biome-ignore lint/complexity/noStaticOnlyClass: groups the grid's service logic in one place
export class JurisdictionGridService {
    static readonly defaultSort: JurisdictionSort = {
        sort_by: "name",
        sort_dir: "asc",
    }

    static readonly keys = {
        tree: ["jurisdictions", "tree"],
        facets: ["jurisdictions", "facets"],
        facetsFor: (mode: JurisdictionMode, filters: JurisdictionFilters) => [
            "jurisdictions",
            "facets",
            mode,
            filters,
        ],
        company: (companyId: string) => ["company", companyId],
        companyIds: (companyId: string) => ["companyJurisdictions", companyId],
        myIds: ["myJurisdictions"],
        admins: (companyId: string) => ["companyAdmins", companyId],
    }

    // Whether any filter is set; the server does the filtering itself
    static hasFilters({ search, byType, status }: JurisdictionFilters) {
        return (
            search.trim() !== "" ||
            pickedTypes(byType).length > 0 ||
            status !== "all"
        )
    }

    static sameTypeFilters(a: TypeFilters, b: TypeFilters) {
        const key = (t: TypeFilters) => JSON.stringify(pickedTypes(t).sort())
        return key(a) === key(b)
    }

    static toApiFilters(filters: JurisdictionFilters): ApiFilters {
        return {
            search: filters.search,
            by_type: filters.byType,
            status: filters.status,
        }
    }

    // Every jurisdiction; only the selection sheet still needs the whole tree
    static treeQuery() {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.tree,
            queryFn: async () =>
                (await JurisdictionsService.readJurisdictionTree()).data.data,
        })
    }

    // Filter options, status tab counts and row totals
    static facetsQuery(mode: JurisdictionMode, filters: JurisdictionFilters) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.facetsFor(mode, filters),
            queryFn: async () =>
                (
                    await JurisdictionsService.readJurisdictionFacets({
                        body: {
                            scope: mode,
                            filters:
                                JurisdictionGridService.toApiFilters(filters),
                        },
                    })
                ).data,
        })
    }

    static async fetchRows(body: JurisdictionRowsQuery) {
        return (await JurisdictionsService.readJurisdictionRows({ body })).data
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

    // Turns a jurisdiction and everything selectable under it on or off; a row
    // without children is a subtree of one
    static saveSubtree(
        mode: JurisdictionMode,
        companyId: string,
        rootId: string,
        enabled: boolean,
    ) {
        const body = { root_id: rootId, enabled }
        return mode === "company"
            ? CompaniesService.toggleCompanyJurisdictionSubtree({
                  path: { company_id: companyId },
                  body,
              })
            : UsersService.toggleMyJurisdictionSubtree({ body })
    }

    // Who would lose an opt-in if the company dropped the subtree; always fresh
    static async affectedUsers(companyId: string, rootId: string) {
        return (
            await CompaniesService.readCompanyJurisdictionAffectedUsers({
                path: { company_id: companyId },
                body: { root_ids: [rootId] },
            })
        ).data.data
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

    // A server row as the grid shows it in this scope
    static toRow(
        r: JurisdictionGridRow,
        { mode, company, user, canEditCompany, admins }: RowInputs,
        highlight?: string,
    ): JurisdictionRow {
        const base = {
            jurisdiction: r,
            mode,
            depth: r.display_depth,
            flagUrl: flagUrlForKeys(r.flag_keys),
            expanded: r.expanded,
            hasChildren: r.has_children,
            checked: r.enabled,
            highlight,
            subtree: r.subtree ?? undefined,
        }
        if (mode === "company") {
            return {
                ...base,
                disabled: !canEditCompany,
                disabledReason: canEditCompany
                    ? undefined
                    : "Only company admins can change this",
                locked: false,
                userCount: r.user_count ?? undefined,
            }
        }
        return {
            ...base,
            disabled: !r.licensed,
            disabledReason: r.licensed
                ? undefined
                : "Not enabled for your license.",
            locked: r.locked,
            unlock: !r.locked
                ? undefined
                : canEditCompany
                  ? { kind: "company" }
                  : JurisdictionGridService.requestUnlock(
                        admins ?? [],
                        r.name,
                        company.name,
                        user,
                    ),
        }
    }
}
