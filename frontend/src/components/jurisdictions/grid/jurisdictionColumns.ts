import type { ColDef } from "ag-grid-community"
import { JurisdictionGridService } from "@/components/jurisdictions/grid/JurisdictionGridService"
import type {
    JurisdictionMode,
    JurisdictionRow,
} from "@/components/jurisdictions/jurisdictionTypes"
import { EnabledCell } from "@/components/jurisdictions/renderers/EnabledCell"
import { NameCell } from "@/components/jurisdictions/renderers/NameCell"

// Rows are updated in place (getRowId), and the grid only re-renders a cell when its
// value changes. Using the whole row as the value makes expanded/checked changes refresh.
const rowValue: ColDef<JurisdictionRow>["valueGetter"] = ({ data }) => data

// The server sorts siblings within each parent: the infinite row model hands the
// grid's sort to the row source, which sends it with every page request

const nameColumn: ColDef<JurisdictionRow> = {
    colId: "name",
    headerName: "Jurisdiction",
    valueGetter: rowValue,
    flex: 1,
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
        width: 160,
        cellRenderer: EnabledCell,
    },
    ...(showUserCounts ? [usersColumn] : []),
]
