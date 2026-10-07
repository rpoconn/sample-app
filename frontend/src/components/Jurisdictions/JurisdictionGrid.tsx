import { ThemeProvider as MuiThemeProvider } from "@mui/material/styles"
import {
    useQuery,
    useQueryClient,
    useSuspenseQuery,
} from "@tanstack/react-query"
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react"

import type { UserPublic } from "@/client"
import { useTheme } from "@/components/theme-provider"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import {
    ConfirmDisableDialog,
    type PendingDisable,
} from "./ConfirmDisableDialog"
import {
    facetsFor,
    filterTree,
    isFiltering,
    statusCounts,
    withFacet,
} from "./filterTree"
import { flagUrlFor, preloadFlags } from "./flags"
import { JurisdictionGridService as Service } from "./JurisdictionGridService"
import { JurisdictionTable } from "./JurisdictionTable"
import { JurisdictionToolbar } from "./JurisdictionToolbar"
import { muiThemes } from "./muiTheme"
import { NoMatches } from "./NoMatches"
import { ScopeBanner } from "./ScopeBanner"
import { SelectionSheet } from "./SelectionSheet"
import { summarizeSelection } from "./selectionSummary"
import type {
    JurisdictionFilters,
    JurisdictionGridContext,
    JurisdictionMode,
    JurisdictionSort,
} from "./types"
import { useExpandedState } from "./useExpandedState"
import { useSelectionMutation } from "./useSelectionMutation"

export type { JurisdictionMode } from "./types"

const noFilters: JurisdictionFilters = {
    search: "",
    byType: {},
    status: "all",
}

export function JurisdictionGrid({
    mode,
    user,
}: {
    mode: JurisdictionMode
    user: UserPublic
}) {
    const queryClient = useQueryClient()
    const { resolvedTheme } = useTheme()
    const { showErrorToast } = useCustomToast()
    const companyId = user.company_id
    const canEditCompany = user.is_superuser || user.company_role === "admin"
    const showUserCounts = mode === "company" && canEditCompany

    const [sort, setSort] = useState<JurisdictionSort>(Service.defaultSort)
    // Kept across scope switches, so the same slice can be compared in both
    const [filters, setFilters] = useState<JurisdictionFilters>(noFilters)
    const search = useDeferredValue(filters.search)
    const [pendingDisable, setPendingDisable] = useState<{
        open: boolean
        item: PendingDisable | null
    }>({ open: false, item: null })
    const [selectionOpen, setSelectionOpen] = useState(false)

    const { data: tree } = useSuspenseQuery(Service.treeQuery(sort, mode))
    const { data: company } = useSuspenseQuery(Service.companyQuery(companyId))
    const { data: companyIds } = useSuspenseQuery(
        Service.companyIdsQuery(companyId),
    )
    const { data: myIds } = useSuspenseQuery(Service.myIdsQuery())
    // Admins only; shows who loses an opt-in before the company drops it
    const { data: userCounts } = useQuery({
        ...Service.userCountsQuery(companyId),
        enabled: canEditCompany,
    })
    // Members only; locked rows offer to email them
    const { data: admins } = useQuery({
        ...Service.adminsQuery(companyId),
        enabled: mode === "user" && !canEditCompany,
    })

    const invalidateUserCounts = () =>
        queryClient.invalidateQueries({
            queryKey: Service.keys.userCounts(companyId),
        })
    const companyMutation = useSelectionMutation(
        Service.keys.companyIds(companyId),
        (ids) => Service.saveCompanyIds(companyId, ids),
        () => {
            // Dropping a company opt-in also drops it for every user in the company
            queryClient.invalidateQueries({ queryKey: Service.keys.myIds })
            invalidateUserCounts()
        },
    )
    const userMutation = useSelectionMutation(
        Service.keys.myIds,
        Service.saveMyIds,
        invalidateUserCounts,
    )

    const byId = useMemo(() => new Map(tree.map((j) => [j.id, j])), [tree])
    const childrenOf = useMemo(() => Service.childrenOf(tree), [tree])

    // Flags depend on ancestors (a state's country), which the cell can't see
    const flagUrls = useMemo(
        () => new Map(tree.map((j) => [j.id, flagUrlFor(j, byId)])),
        [tree, byId],
    )
    useEffect(() => preloadFlags(flagUrls.values()), [flagUrls])

    const enabledIds = useMemo(
        () => new Set(mode === "company" ? companyIds : myIds),
        [mode, companyIds, myIds],
    )
    // The company's license; users can only turn these on
    const licensedIds = useMemo(() => new Set(companyIds), [companyIds])
    const selectionGroups = useMemo(
        () =>
            summarizeSelection(childrenOf, byId, flagUrls, enabledIds, (j) =>
                Service.isSelectable(j, mode, licensedIds),
            ),
        [childrenOf, byId, flagUrls, enabledIds, licensedIds, mode],
    )
    const filtered = useMemo(
        () =>
            filterTree(
                tree,
                byId,
                { search, byType: filters.byType, status: filters.status },
                enabledIds,
                licensedIds,
            ),
        [
            tree,
            byId,
            search,
            filters.byType,
            filters.status,
            enabledIds,
            licensedIds,
        ],
    )
    const counts = useMemo(
        () =>
            statusCounts(
                tree,
                byId,
                { search, byType: filters.byType },
                enabledIds,
                licensedIds,
            ),
        [tree, byId, search, filters.byType, enabledIds, licensedIds],
    )
    const facets = useMemo(
        () => facetsFor(tree, byId, filters.byType, flagUrls),
        [tree, byId, filters.byType, flagUrls],
    )

    const { expanded, updateExpanded } = useExpandedState(tree, filtered)

    const { rows, summary } = useMemo(
        () =>
            Service.buildRows({
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
            }),
        [
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
        ],
    )

    // The grid may keep the first context it is given, so handlers read live state via a ref
    const latest = useRef({
        mode,
        byId,
        childrenOf,
        companyId,
        companyIds,
        myIds,
        companyMutation,
        userMutation,
        updateExpanded,
        showErrorToast,
    })
    latest.current = {
        mode,
        byId,
        childrenOf,
        companyId,
        companyIds,
        myIds,
        companyMutation,
        userMutation,
        updateExpanded,
        showErrorToast,
    }

    const context = useMemo<JurisdictionGridContext>(() => {
        // Saves ids on or off in one request. Turning company opt-ins off asks
        // first when users would lose them; named after the clicked row.
        const apply = async (
            rowId: string,
            ids: string[],
            enabled: boolean,
        ) => {
            const { mode, companyId, showErrorToast } = latest.current
            if (mode === "company" && !enabled) {
                // Fetch fresh: someone may have opted in since the page loaded
                let users: PendingDisable["users"]
                try {
                    users = await Service.affectedUsers(companyId, ids)
                } catch (err) {
                    handleError.call(showErrorToast, err as Error)
                    return
                }
                if (users.length > 0) {
                    const name = latest.current.byId.get(rowId)?.name ?? ""
                    setPendingDisable({
                        open: true,
                        item: { ids, name, users },
                    })
                    return
                }
            }
            const l = latest.current
            if (l.mode === "company") {
                l.companyMutation.mutate(
                    Service.nextIds(l.companyIds, ids, enabled),
                )
            } else {
                l.userMutation.mutate(Service.nextIds(l.myIds, ids, enabled))
            }
        }
        return {
            toggleExpanded: (id) =>
                latest.current.updateExpanded((prev) => {
                    const next = new Set(prev)
                    if (!next.delete(id)) next.add(id)
                    return next
                }),
            toggleEnabled: (id, enabled) => apply(id, [id], enabled),
            toggleSubtree: (id, enabled) => {
                const { mode, byId, childrenOf, companyIds } = latest.current
                const root = byId.get(id)
                if (!root) return
                const companySet = new Set(companyIds)
                const ids = Service.subtreeOf(childrenOf, root)
                    .filter((j) => Service.isSelectable(j, mode, companySet))
                    .map((j) => j.id)
                if (ids.length > 0) apply(id, ids, enabled)
            },
        }
    }, [])

    return (
        <MuiThemeProvider
            theme={resolvedTheme === "dark" ? muiThemes.dark : muiThemes.light}
        >
            <div className="flex flex-col gap-4">
                <ScopeBanner
                    mode={mode}
                    canEditCompany={canEditCompany}
                    lockedCount={summary.locked ?? 0}
                />
                <JurisdictionToolbar
                    mode={mode}
                    search={filters.search}
                    onSearchChange={(value) =>
                        setFilters((f) => ({ ...f, search: value }))
                    }
                    status={filters.status}
                    counts={counts}
                    onStatusChange={(status) =>
                        setFilters((f) => ({ ...f, status }))
                    }
                    facets={facets}
                    onFacetChange={(type, ids) =>
                        setFilters((f) => ({
                            ...f,
                            byType: withFacet(tree, byId, f.byType, type, ids),
                        }))
                    }
                    filtering={!!filtered}
                    onClear={() => setFilters(noFilters)}
                    summary={summary}
                    onExpandAll={() =>
                        updateExpanded(
                            () =>
                                new Set(
                                    tree
                                        .filter((j) => (j.child_count ?? 0) > 0)
                                        .map((j) => j.id),
                                ),
                        )
                    }
                    onCollapseAll={() => updateExpanded(() => new Set())}
                    onViewSelection={() => setSelectionOpen(true)}
                />
                <div className="relative h-[max(24rem,calc(100vh-26rem))] overflow-hidden rounded-md">
                    <JurisdictionTable
                        rows={rows}
                        mode={mode}
                        showUserCounts={showUserCounts}
                        context={context}
                        onSortChange={setSort}
                    />
                    {filtered && rows.length === 0 && (
                        <NoMatches
                            allTaken={
                                filters.status === "available" &&
                                licensedIds.size > 0 &&
                                !isFiltering({ ...filters, status: "all" })
                            }
                            onClear={() => setFilters(noFilters)}
                        />
                    )}
                </div>
                <SelectionSheet
                    open={selectionOpen}
                    onOpenChange={setSelectionOpen}
                    mode={mode}
                    ownerId={mode === "company" ? companyId : user.id}
                    groups={selectionGroups}
                    ids={mode === "company" ? companyIds : myIds}
                />
                <ConfirmDisableDialog
                    open={pendingDisable.open}
                    pending={pendingDisable.item}
                    companyName={company.name}
                    onCancel={() =>
                        setPendingDisable((p) => ({ ...p, open: false }))
                    }
                    onConfirm={(item) => {
                        setPendingDisable((p) => ({ ...p, open: false }))
                        companyMutation.mutate(
                            Service.nextIds(companyIds, item.ids, false),
                        )
                    }}
                />
            </div>
        </MuiThemeProvider>
    )
}

export default JurisdictionGrid
