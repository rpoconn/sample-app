import { ThemeProvider as MuiThemeProvider } from "@mui/material/styles"
import {
    useQuery,
    useQueryClient,
    useSuspenseQuery,
} from "@tanstack/react-query"
import type { AgGridReact } from "ag-grid-react"
import {
    useCallback,
    useDeferredValue,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react"

import type { UserPublic } from "@/client"
import { useTheme } from "@/components/theme-provider"
import useCustomToast from "@/hooks/useCustomToast"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import { handleError } from "@/utils"
import {
    ConfirmDisableDialog,
    type PendingDisable,
} from "./ConfirmDisableDialog"
import { JurisdictionGridService as Service } from "./JurisdictionGridService"
import { JurisdictionRowSource, type RowMapper } from "./JurisdictionRowSource"
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
    JurisdictionRow,
    TypeFilters,
} from "./types"
import { useSelectionMutation } from "./useSelectionMutation"

export type { JurisdictionMode } from "./types"

const noFilters: JurisdictionFilters = {
    search: "",
    byType: {},
    status: "all",
}

const searchDelay = 300
const searchSettled = (prev: JurisdictionFilters, next: JurisdictionFilters) =>
    prev.search === next.search || next.search === ""

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

    // Kept across scope switches, so the same slice can be compared in both
    const [filters, setFilters] = useState<JurisdictionFilters>(noFilters)
    // What the server filters by; the current rows and counts stay up meanwhile.
    // Typing waits for a pause; everything else, clearing included, goes now.
    const queried = useDeferredValue(
        useDebouncedValue(filters, searchDelay, searchSettled),
    )
    const [pendingDisable, setPendingDisable] = useState<{
        open: boolean
        item: PendingDisable | null
    }>({ open: false, item: null })
    const [selectionOpen, setSelectionOpen] = useState(false)
    const gridRef = useRef<AgGridReact<JurisdictionRow>>(null)

    const { data: company } = useSuspenseQuery(Service.companyQuery(companyId))
    const {
        data: { jurisdiction_ids: companyIds },
    } = useSuspenseQuery(Service.companyIdsQuery(companyId))
    const {
        data: { jurisdiction_ids: myIds },
    } = useSuspenseQuery(Service.myIdsQuery())
    const { data: facets } = useSuspenseQuery(
        Service.facetsQuery(mode, queried),
    )
    // Members only; locked rows offer to email them
    const { data: admins } = useQuery({
        ...Service.adminsQuery(companyId),
        enabled: mode === "user" && !canEditCompany,
    })
    // The sheet rolls fully-on subtrees up, which takes the whole tree; loaded
    // only once it's opened
    const { data: tree } = useQuery({
        ...Service.treeQuery(),
        enabled: selectionOpen,
    })

    const toRow = useCallback<RowMapper>(
        (r, highlight) =>
            Service.toRow(
                r,
                { mode, company, user, canEditCompany, admins },
                highlight,
            ),
        [mode, company, user, canEditCompany, admins],
    )
    const [source] = useState(
        () =>
            new JurisdictionRowSource(mode, queried, toRow, (err) =>
                handleError.call(showErrorToast, err as Error),
            ),
    )

    // New filters reload the rows from the top
    useEffect(() => {
        if (!source.setQuery(mode, queried)) return
        const api = gridRef.current?.api
        if (!api) return
        if (api.getDisplayedRowCount() > 0) api.ensureIndexVisible(0, "top")
        api.purgeInfiniteCache()
    }, [source, mode, queried])

    // Loaded rows are mapped again when what the mapping reads changes
    useEffect(() => {
        if (source.toRow === toRow) return
        source.toRow = toRow
        gridRef.current?.api.forEachNode((node) => {
            if (node.data) {
                node.setData(toRow(node.data.jurisdiction, node.data.highlight))
            }
        })
    }, [source, toRow])

    // Picks the server dropped, because a coarser facet no longer covers them,
    // leave the filters too, so they don't come back with the coarser pick
    useEffect(() => {
        const pruned = facets.by_type as TypeFilters
        if (Service.sameTypeFilters(pruned, queried.byType)) return
        setFilters((f) =>
            f.byType === queried.byType ? { ...f, byType: pruned } : f,
        )
    }, [facets, queried.byType])

    // Turning company opt-ins off asks first when users would lose them; named
    // after the clicked row. Reads live state via a ref, so it never changes.
    const apply = useCallback(
        async (rowId: string, enabled: boolean, subtree: boolean) => {
            const { mode, companyId, showErrorToast } = latest.current
            if (mode === "company" && !enabled) {
                // Fetch fresh: someone may have opted in since the page loaded
                let preview: Awaited<ReturnType<typeof Service.previewDisable>>
                try {
                    preview = await Service.previewDisable(companyId, rowId)
                } catch (err) {
                    handleError.call(showErrorToast, err as Error)
                    return
                }
                if (preview.users.length > 0) {
                    const name =
                        gridRef.current?.api.getRowNode(rowId)?.data
                            ?.jurisdiction.name ?? ""
                    setPendingDisable({
                        open: true,
                        item: { rootId: rowId, subtree, name, ...preview },
                    })
                    return
                }
            }
            latest.current.save(rowId, enabled, subtree)
        },
        [],
    )

    const mutation = useSelectionMutation(
        mode,
        companyId,
        () => {
            queryClient.invalidateQueries({ queryKey: Service.keys.facets })
            queryClient.invalidateQueries({
                queryKey: Service.keys.companyIds(companyId),
            })
            // Dropping a company opt-in also drops it for every user in the company
            queryClient.invalidateQueries({ queryKey: Service.keys.myIds })
            // Ancestors' select-all counts and user counts change too
            gridRef.current?.api.refreshInfiniteCache()
        },
        // The license moved on while the dialog was open: review it again
        ({ rootId, enabled, subtree }) => apply(rootId, enabled, subtree),
    )

    // Saves a row, or the row and everything under it. A single row's switch
    // flips right away; the refresh after saving settles the rest. A version
    // only commits if the license is still at it.
    const save = (
        rootId: string,
        enabled: boolean,
        subtree: boolean,
        version?: number,
    ) => {
        const node = gridRef.current?.api.getRowNode(rootId)
        if (!subtree && node?.data) {
            node.setData({ ...node.data, checked: enabled })
        }
        mutation.mutate({ rootId, enabled, subtree, version })
    }

    // The grid may keep the first context it is given, so handlers read live state via a ref
    const latest = useRef({ mode, companyId, save, showErrorToast })
    latest.current = { mode, companyId, save, showErrorToast }

    const context = useMemo<JurisdictionGridContext>(
        () => ({
            toggleExpanded: (id) => {
                if (source.toggleExpanded(id)) {
                    gridRef.current?.api.refreshInfiniteCache()
                }
            },
            toggleEnabled: (id, enabled) => apply(id, enabled, false),
            toggleSubtree: (id, enabled) => apply(id, enabled, true),
        }),
        [source, apply],
    )

    const enabledIds = mode === "company" ? companyIds : myIds
    const selectionEntries = useMemo(() => {
        if (!tree) return undefined
        const licensed = new Set(companyIds)
        return summarizeSelection(
            tree,
            new Set(enabledIds),
            (j) =>
                !j.is_structural && (mode === "company" || licensed.has(j.id)),
        )
    }, [tree, enabledIds, companyIds, mode])

    // Shows the live picks while the server catches up; drops any that are no
    // longer among a facet's options
    const toolbarFacets = useMemo(
        () =>
            facets.facets.map((f) => ({
                ...f,
                value: (filters.byType[f.type] ?? []).filter((id) =>
                    f.options.some((o) => o.id === id),
                ),
            })),
        [facets, filters.byType],
    )

    const reload = () => gridRef.current?.api.refreshInfiniteCache()

    return (
        <MuiThemeProvider
            theme={resolvedTheme === "dark" ? muiThemes.dark : muiThemes.light}
        >
            <div className="flex flex-col gap-4">
                <ScopeBanner
                    mode={mode}
                    canEditCompany={canEditCompany}
                    lockedCount={facets.summary.locked ?? 0}
                />
                <JurisdictionToolbar
                    mode={mode}
                    search={filters.search}
                    onSearchChange={(value) =>
                        setFilters((f) => ({ ...f, search: value }))
                    }
                    status={filters.status}
                    counts={facets.status_counts}
                    onStatusChange={(status) =>
                        setFilters((f) => ({ ...f, status }))
                    }
                    facets={toolbarFacets}
                    onFacetChange={(type, ids) =>
                        setFilters((f) => ({
                            ...f,
                            byType: { ...f.byType, [type]: ids },
                        }))
                    }
                    filtering={Service.hasFilters(filters)}
                    onClear={() => setFilters(noFilters)}
                    onExpandAll={() => {
                        source.expandAll()
                        reload()
                    }}
                    onCollapseAll={() => {
                        source.collapseAll()
                        reload()
                    }}
                    onViewSelection={() => setSelectionOpen(true)}
                />
                <div className="relative overflow-hidden rounded-md">
                    <JurisdictionTable
                        gridRef={gridRef}
                        datasource={source}
                        mode={mode}
                        showUserCounts={showUserCounts}
                        context={context}
                    />
                    {/* Ancestors only show above a match, so no matches means no rows */}
                    {Service.hasFilters(queried) &&
                        facets.summary.shown === 0 && (
                            <NoMatches
                                allTaken={
                                    queried.status === "available" &&
                                    companyIds.length > 0 &&
                                    !Service.hasFilters({
                                        ...queried,
                                        status: "all",
                                    })
                                }
                                onClear={() => setFilters(noFilters)}
                            />
                        )}
                </div>
                <SelectionSheet
                    open={selectionOpen}
                    onOpenChange={setSelectionOpen}
                    mode={mode}
                    entries={selectionEntries}
                    count={enabledIds.length}
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
                        save(item.rootId, false, item.subtree, item.version)
                    }}
                />
            </div>
        </MuiThemeProvider>
    )
}

export default JurisdictionGrid
