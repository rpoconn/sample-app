import {
    AllCommunityModule,
    colorSchemeDark,
    colorSchemeLight,
    type IDatasource,
    ModuleRegistry,
    themeQuartz,
} from "ag-grid-community"
import { AgGridReact } from "ag-grid-react"
import { type RefObject, useMemo, useState } from "react"

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

// The grid's wrapper border, above and below, and the header's bottom border
const borderHeight = 3

// Body kept open with no rows, for the no-matches message over it
const emptyBodyHeight = 192

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
    // Header plus the rows there are, so short lists don't leave an empty body
    const [fitHeight, setFitHeight] = useState<number>()

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
        <div
            className="h-[max(24rem,calc(100vh-26rem))] max-h-[max(24rem,calc(100vh-26rem))]"
            style={{ height: fitHeight }}
        >
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
                onModelUpdated={({ api }) => {
                    const { headerHeight, rowHeight } =
                        api.getSizesForCurrentTheme()
                    const rows = api.getDisplayedRowCount()
                    setFitHeight(
                        headerHeight +
                            (rows > 0 ? rows * rowHeight : emptyBodyHeight) +
                            borderHeight,
                    )
                }}
                suppressCellFocus
            />
        </div>
    )
}

export default JurisdictionTable
