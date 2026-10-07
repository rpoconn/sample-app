import {
    AllCommunityModule,
    colorSchemeDark,
    colorSchemeLight,
    ModuleRegistry,
    themeQuartz,
} from "ag-grid-community"
import { AgGridReact } from "ag-grid-react"
import { startTransition, useMemo } from "react"

import { useTheme } from "@/components/theme-provider"
import { columnsFor } from "./columns"
import { JurisdictionGridService } from "./JurisdictionGridService"
import type {
    JurisdictionGridContext,
    JurisdictionMode,
    JurisdictionRow,
    JurisdictionSort,
} from "./types"

ModuleRegistry.registerModules([AllCommunityModule])

const { defaultSort } = JurisdictionGridService

export function JurisdictionTable({
    rows,
    mode,
    showUserCounts,
    context,
    onSortChange,
}: {
    rows: JurisdictionRow[]
    mode: JurisdictionMode
    showUserCounts: boolean
    context: JurisdictionGridContext
    onSortChange: (sort: JurisdictionSort) => void
}) {
    const { resolvedTheme } = useTheme()

    const columnDefs = useMemo(
        () => columnsFor(mode, showUserCounts),
        [mode, showUserCounts],
    )

    const theme = useMemo(
        () =>
            themeQuartz.withPart(
                resolvedTheme === "dark" ? colorSchemeDark : colorSchemeLight,
            ),
        [resolvedTheme],
    )

    return (
        <AgGridReact<JurisdictionRow>
            theme={theme}
            rowData={rows}
            columnDefs={columnDefs}
            context={context}
            getRowId={({ data }) => data.jurisdiction.id}
            getRowClass={({ data }) =>
                data?.locked ? "opacity-60 bg-muted/40" : undefined
            }
            suppressNoRowsOverlay
            onSortChanged={({ api }) => {
                const col = api.getColumnState().find((c) => c.sort != null)
                if (!col?.sort) {
                    // Clearing the enabled sort falls back to the default; this
                    // fires onSortChanged again with the name column sorted
                    api.applyColumnState({
                        state: [
                            {
                                colId: defaultSort.sort_by,
                                sort: defaultSort.sort_dir,
                            },
                        ],
                    })
                    return
                }
                // Keep the current rows on screen while the re-sorted tree loads
                startTransition(() =>
                    onSortChange({
                        sort_by: col.colId as JurisdictionSort["sort_by"],
                        sort_dir: col.sort as JurisdictionSort["sort_dir"],
                    }),
                )
            }}
            suppressCellFocus
        />
    )
}

export default JurisdictionTable
