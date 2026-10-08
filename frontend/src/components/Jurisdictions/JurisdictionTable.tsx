import {
    AllCommunityModule,
    colorSchemeDark,
    colorSchemeLight,
    type IDatasource,
    ModuleRegistry,
    themeQuartz,
} from "ag-grid-community"
import { AgGridReact } from "ag-grid-react"
import { type RefObject, useMemo } from "react"

import { useTheme } from "@/components/theme-provider"
import { columnsFor } from "./columns"
import { JurisdictionGridService } from "./JurisdictionGridService"
import type {
    JurisdictionGridContext,
    JurisdictionMode,
    JurisdictionRow,
} from "./types"

ModuleRegistry.registerModules([AllCommunityModule])

const { defaultSort } = JurisdictionGridService

// Rows per page request
const pageSize = 100

export function JurisdictionTable({
    gridRef,
    datasource,
    mode,
    showUserCounts,
    context,
}: {
    gridRef: RefObject<AgGridReact<JurisdictionRow> | null>
    // Pages of rows, filtered and sorted on the server
    datasource: IDatasource
    mode: JurisdictionMode
    showUserCounts: boolean
    context: JurisdictionGridContext
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
            ref={gridRef}
            theme={theme}
            rowModelType="infinite"
            datasource={datasource}
            cacheBlockSize={pageSize}
            columnDefs={columnDefs}
            context={context}
            getRowId={({ data }) => data.jurisdiction.id}
            getRowClass={({ data }) =>
                data?.locked ? "opacity-60 bg-muted/40" : undefined
            }
            suppressNoRowsOverlay
            onSortChanged={({ api }) => {
                // Clearing the enabled sort falls back to the default. Any other
                // change reloads the rows from the server with the new sort.
                if (api.getColumnState().some((c) => c.sort != null)) return
                api.applyColumnState({
                    state: [
                        {
                            colId: defaultSort.sort_by,
                            sort: defaultSort.sort_dir,
                        },
                    ],
                })
            }}
            suppressCellFocus
        />
    )
}

export default JurisdictionTable
