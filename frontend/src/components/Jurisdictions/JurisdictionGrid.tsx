import {
    useMutation,
    useQueryClient,
    useSuspenseQuery,
} from "@tanstack/react-query"
import {
    AllCommunityModule,
    type ColDef,
    colorSchemeDark,
    colorSchemeLight,
    ModuleRegistry,
    themeQuartz,
} from "ag-grid-community"
import { AgGridReact } from "ag-grid-react"
import { useMemo, useRef, useState } from "react"

import {
    CompaniesService,
    type JurisdictionPublic,
    JurisdictionsService,
    type UserPublic,
    UsersService,
} from "@/client"
import { useTheme } from "@/components/theme-provider"
import { Button } from "@/components/ui/button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"
import { EnabledCell } from "./EnabledCell"
import { NameCell } from "./NameCell"
import type {
    JurisdictionGridContext,
    JurisdictionMode,
    JurisdictionRow,
} from "./types"

export type { JurisdictionMode } from "./types"

ModuleRegistry.registerModules([AllCommunityModule])

const treeQueryKey = ["jurisdictions", "tree"]
const myQueryKey = ["myJurisdictions"]
const companyQueryKey = (companyId: string) => [
    "companyJurisdictions",
    companyId,
]

const columnDefs: ColDef<JurisdictionRow>[] = [
    {
        headerName: "Jurisdiction",
        field: "jurisdiction.name",
        flex: 1,
        sortable: false,
        cellRenderer: NameCell,
    },
    {
        headerName: "Enabled",
        width: 120,
        sortable: false,
        cellRenderer: EnabledCell,
    },
]

function useSelectionMutation(
    queryKey: string[],
    save: (ids: string[]) => Promise<unknown>,
    onSaved?: () => void,
) {
    const queryClient = useQueryClient()
    const { showErrorToast } = useCustomToast()

    return useMutation({
        mutationFn: save,
        onMutate: async (ids) => {
            await queryClient.cancelQueries({ queryKey })
            const previous = queryClient.getQueryData<string[]>(queryKey)
            queryClient.setQueryData(queryKey, ids)
            return { previous }
        },
        onError: (err, _ids, ctx) => {
            queryClient.setQueryData(queryKey, ctx?.previous)
            handleError.call(showErrorToast, err)
        },
        onSettled: () => {
            queryClient.invalidateQueries({ queryKey })
            onSaved?.()
        },
    })
}

const idsOf = (res: { data: { data: JurisdictionPublic[] } }) =>
    res.data.data.map((j) => j.id)

export function JurisdictionGrid({
    mode,
    user,
}: {
    mode: JurisdictionMode
    user: UserPublic
}) {
    const queryClient = useQueryClient()
    const { resolvedTheme } = useTheme()
    const companyId = user.company_id
    const canEditCompany = user.is_superuser || user.company_role === "admin"

    const { data: tree } = useSuspenseQuery({
        queryKey: treeQueryKey,
        queryFn: async () =>
            (await JurisdictionsService.readJurisdictionTree()).data.data,
    })
    const { data: companyIds } = useSuspenseQuery({
        queryKey: companyQueryKey(companyId),
        queryFn: async () =>
            idsOf(
                await CompaniesService.readCompanyJurisdictions({
                    path: { company_id: companyId },
                }),
            ),
    })
    const { data: myIds } = useSuspenseQuery({
        queryKey: myQueryKey,
        queryFn: async () => idsOf(await UsersService.readMyJurisdictions()),
    })

    const companyMutation = useSelectionMutation(
        companyQueryKey(companyId),
        (ids) =>
            CompaniesService.setCompanyJurisdictions({
                path: { company_id: companyId },
                body: { jurisdiction_ids: ids },
            }),
        // Dropping a company opt-in also drops it for every user in the company
        () => queryClient.invalidateQueries({ queryKey: myQueryKey }),
    )
    const userMutation = useSelectionMutation(myQueryKey, (ids) =>
        UsersService.setMyJurisdictions({ body: { jurisdiction_ids: ids } }),
    )

    const childrenOf = useMemo(() => {
        const map = new Map<string | null, JurisdictionPublic[]>()
        for (const j of tree) {
            const key = j.parent_id ?? null
            map.set(key, [...(map.get(key) ?? []), j])
        }
        for (const siblings of map.values()) {
            siblings.sort(
                (a, b) =>
                    a.sort_order - b.sort_order || a.name.localeCompare(b.name),
            )
        }
        return map
    }, [tree])

    const [expanded, setExpanded] = useState<Set<string>>(
        () => new Set(tree.filter((j) => j.parent_id == null).map((j) => j.id)),
    )

    const rows = useMemo(() => {
        const companySet = new Set(companyIds)
        const mySet = new Set(myIds)
        const result: JurisdictionRow[] = []
        const walk = (parentId: string | null) => {
            for (const j of childrenOf.get(parentId) ?? []) {
                const isExpanded = expanded.has(j.id)
                let row: JurisdictionRow
                if (mode === "company") {
                    row = {
                        jurisdiction: j,
                        expanded: isExpanded,
                        checked: companySet.has(j.id),
                        disabled: !canEditCompany,
                        disabledReason: canEditCompany
                            ? undefined
                            : "Only company admins can change this",
                    }
                } else {
                    const allowed = companySet.has(j.id)
                    row = {
                        jurisdiction: j,
                        expanded: isExpanded,
                        checked: mySet.has(j.id),
                        disabled: !allowed,
                        disabledReason: allowed
                            ? undefined
                            : "Not enabled for your company",
                    }
                }
                result.push(row)
                if (isExpanded) walk(j.id)
            }
        }
        walk(null)
        return result
    }, [childrenOf, expanded, mode, companyIds, myIds, canEditCompany])

    // The grid may keep the first context it is given, so handlers read live state via a ref
    const latest = useRef({
        mode,
        companyIds,
        myIds,
        companyMutation,
        userMutation,
    })
    latest.current = { mode, companyIds, myIds, companyMutation, userMutation }

    const context = useMemo<JurisdictionGridContext>(
        () => ({
            toggleExpanded: (id) =>
                setExpanded((prev) => {
                    const next = new Set(prev)
                    if (!next.delete(id)) next.add(id)
                    return next
                }),
            toggleEnabled: (id, enabled) => {
                const l = latest.current
                const [current, mutation] =
                    l.mode === "company"
                        ? [l.companyIds, l.companyMutation]
                        : [l.myIds, l.userMutation]
                const next = enabled
                    ? [...new Set([...current, id])]
                    : current.filter((x) => x !== id)
                mutation.mutate(next)
            },
        }),
        [],
    )

    const theme = useMemo(
        () =>
            themeQuartz.withPart(
                resolvedTheme === "dark" ? colorSchemeDark : colorSchemeLight,
            ),
        [resolvedTheme],
    )

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between gap-4">
                <p className="text-sm text-muted-foreground">
                    {mode === "company"
                        ? canEditCompany
                            ? "Choose which jurisdictions your company opts into. Users can only enable these."
                            : "Jurisdictions your company has opted into. Only company admins can change these."
                        : "Choose your jurisdictions. Only those your company has opted into can be enabled."}
                </p>
                <div className="flex shrink-0 gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                            setExpanded(
                                new Set(
                                    tree
                                        .filter((j) => (j.child_count ?? 0) > 0)
                                        .map((j) => j.id),
                                ),
                            )
                        }
                    >
                        Expand all
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setExpanded(new Set())}
                    >
                        Collapse all
                    </Button>
                </div>
            </div>
            <div className="h-[calc(100vh-260px)] min-h-[320px]">
                <AgGridReact<JurisdictionRow>
                    theme={theme}
                    rowData={rows}
                    columnDefs={columnDefs}
                    context={context}
                    getRowId={({ data }) => data.jurisdiction.id}
                    suppressCellFocus
                />
            </div>
        </div>
    )
}

export default JurisdictionGrid
