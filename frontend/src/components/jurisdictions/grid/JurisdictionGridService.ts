import { queryOptions } from "@tanstack/react-query"

import {
    type JurisdictionFilters as ApiFilters,
    CompaniesService,
    type CompanyAdmin,
    type CompanyPublic,
    type JurisdictionGridRow,
    type JurisdictionRowsQuery,
    JurisdictionsService,
    type SelectionChange,
    type UserPublic,
    UsersService,
    ViewsService,
} from "@/client"
import { flagUrlForKeys } from "@/components/jurisdictions/flags"
import type {
    JurisdictionFilters,
    JurisdictionMode,
    JurisdictionRow,
    JurisdictionSort,
    TypeFilters,
    Unlock,
} from "@/components/jurisdictions/jurisdictionTypes"

// What a server row's grid state depends on beyond the row itself
export type RowInputs = {
    mode: JurisdictionMode
    company: CompanyPublic
    user: UserPublic
    canEditCompany: boolean
    admins?: CompanyAdmin[]
}

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
                    await ViewsService.readJurisdictionFacets({
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
        return (await ViewsService.readJurisdictionRows({ body })).data
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

    // The company's opt-ins and the version they're at
    static companyIdsQuery(companyId: string) {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.companyIds(companyId),
            queryFn: async () =>
                (
                    await CompaniesService.readCompanyJurisdictions({
                        path: { company_id: companyId },
                    })
                ).data,
        })
    }

    static myIdsQuery() {
        return queryOptions({
            queryKey: JurisdictionGridService.keys.myIds,
            queryFn: async () =>
                (await UsersService.readMyJurisdictions()).data,
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

    // Turns a jurisdiction on or off, or with subtree, it and everything selectable
    // under it. With a version, the save only lands if nothing changed since then
    // (412 otherwise).
    static saveSelection(
        mode: JurisdictionMode,
        companyId: string,
        rootId: string,
        enabled: boolean,
        subtree: boolean,
        version?: number,
    ) {
        const body = JurisdictionGridService.changeFor(rootId, enabled, subtree)
        const headers =
            version === undefined ? undefined : { "If-Match": String(version) }
        return mode === "company"
            ? CompaniesService.patchCompanyJurisdictions({
                  path: { company_id: companyId },
                  body,
                  headers,
              })
            : UsersService.patchMyJurisdictions({ body, headers })
    }

    // Who would lose an opt-in if the company dropped the row (or its subtree),
    // and the version to commit exactly that against; always fresh
    static async previewDisable(
        companyId: string,
        rootId: string,
        subtree: boolean,
    ) {
        const { data } = await CompaniesService.previewCompanyJurisdictions({
            path: { company_id: companyId },
            body: JurisdictionGridService.changeFor(rootId, false, subtree),
        })
        return { version: data.version, users: data.affected_users.data }
    }

    private static changeFor(
        rootId: string,
        enabled: boolean,
        subtree: boolean,
    ): SelectionChange {
        if (subtree) {
            return enabled
                ? { add_subtrees: [rootId] }
                : { remove_subtrees: [rootId] }
        }
        return enabled ? { add: [rootId] } : { remove: [rootId] }
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
            `You can turn it on here: ${window.location.origin}/companyAdmin`,
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
        // A grouping is locked when nothing under it can be enabled
        const locked = r.locked || (!!r.is_structural && r.subtree?.total === 0)
        return {
            ...base,
            disabled: !r.licensed,
            disabledReason: r.licensed
                ? undefined
                : "Not enabled for your license.",
            locked,
            unlock: !locked
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
