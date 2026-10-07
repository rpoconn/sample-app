import type { ColDef } from "ag-grid-community"

import { EnabledCell } from "./EnabledCell"
import { JurisdictionGridService } from "./JurisdictionGridService"
import { NameCell } from "./NameCell"
import type { JurisdictionMode, JurisdictionRow } from "./types"

// Rows are updated in place (getRowId), and the grid only re-renders a cell when its
// value changes. Using the whole row as the value makes expanded/checked changes refresh.
const rowValue: ColDef<JurisdictionRow>["valueGetter"] = ({ data }) => data

// The server sorts siblings within each parent; a client-side sort would break the
// tree apart. Headers stay clickable for the arrow, but the (stable) sort is a no-op.
const serverSorted = () => 0

const nameColumn: ColDef<JurisdictionRow> = {
    colId: "name",
    headerName: "Jurisdiction",
    valueGetter: rowValue,
    flex: 1,
    comparator: serverSorted,
    initialSort: JurisdictionGridService.defaultSort.sort_dir,
    // Name is the default sort, so it toggles direction rather than clearing
    sortingOrder: ["asc", "desc"],
    cellRenderer: NameCell,
}

const usersColumn: ColDef<JurisdictionRow> = {
    colId: "users",
    headerName: "Users",
    headerTooltip: "Users at your company who have selected this jurisdiction",
    valueGetter: ({ data }) =>
        data?.jurisdiction.is_structural ? null : data?.userCount,
    width: 100,
    sortable: false,
    cellClassRules: { "text-muted-foreground": ({ value }) => !value },
}

export const columnsFor = (
    mode: JurisdictionMode,
    showUserCounts: boolean,
): ColDef<JurisdictionRow>[] => [
    nameColumn,
    {
        colId: "enabled",
        headerName:
            mode === "company" ? "Enabled for company" : "Enabled for me",
        valueGetter: rowValue,
        width: 180,
        comparator: serverSorted,
        cellRenderer: EnabledCell,
    },
    ...(showUserCounts ? [usersColumn] : []),
]
