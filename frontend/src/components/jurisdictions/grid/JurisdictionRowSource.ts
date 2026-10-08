import type { IDatasource, IGetRowsParams } from "ag-grid-community"

import type { JurisdictionGridRow } from "@/client"
import { preloadFlags } from "@/components/jurisdictions/flags"
import { JurisdictionGridService as Service } from "@/components/jurisdictions/grid/JurisdictionGridService"
import type {
    JurisdictionFilters,
    JurisdictionMode,
    JurisdictionRow,
    JurisdictionSort,
} from "@/components/jurisdictions/jurisdictionTypes"

export type RowMapper = (
    r: JurisdictionGridRow,
    highlight?: string,
) => JurisdictionRow

// Rows opened in the view. ids null asks the server for its default: the roots, or
// when filtering, the ancestors of every match. all opens every row with children.
type Expansion = { ids: string[] | null; all: boolean }

const serverDefault = (): Expansion => ({ ids: null, all: false })

// Feeds the grid's infinite row model from POST /views/jurisdiction-grid/rows, one
// block per request. Browsing and filtering keep separate expansion: a filter opens
// the ancestors of its matches, and clearing it returns to what was open before.
export class JurisdictionRowSource implements IDatasource {
    private mode: JurisdictionMode
    private filters: JurisdictionFilters
    private browse = serverDefault()
    private filtered = serverDefault()
    // Swapped when what the mapping reads changes (e.g. admins load)
    toRow: RowMapper
    private onError: (err: unknown) => void

    constructor(
        mode: JurisdictionMode,
        filters: JurisdictionFilters,
        toRow: RowMapper,
        onError: (err: unknown) => void,
    ) {
        this.mode = mode
        this.filters = filters
        this.toRow = toRow
        this.onError = onError
    }

    private get expansion() {
        return Service.hasFilters(this.filters) ? this.filtered : this.browse
    }

    private set expansion(next: Expansion) {
        if (Service.hasFilters(this.filters)) this.filtered = next
        else this.browse = next
    }

    // Whether the rows changed, so the grid should reload them from the top
    setQuery(mode: JurisdictionMode, filters: JurisdictionFilters) {
        if (mode === this.mode && filters === this.filters) return false
        if (mode !== this.mode) this.browse = serverDefault()
        this.mode = mode
        this.filters = filters
        this.filtered = serverDefault()
        return true
    }

    // Whether anything changed. Ignored while the server is still working out
    // which rows are open, which is only until the first rows load.
    toggleExpanded(id: string) {
        const { ids } = this.expansion
        if (!ids) return false
        this.expansion = {
            ids: ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id],
            all: false,
        }
        return true
    }

    expandAll() {
        this.expansion = { ids: null, all: true }
    }

    collapseAll() {
        this.expansion = { ids: [], all: false }
    }

    getRows(params: IGetRowsParams) {
        const sent = this.expansion
        const [sort] = params.sortModel
        const highlight = this.filters.search.trim() || undefined
        Service.fetchRows({
            scope: this.mode,
            filters: Service.toApiFilters(this.filters),
            sort_by: (sort?.colId as JurisdictionSort["sort_by"]) ?? null,
            sort_dir: sort?.sort ?? "asc",
            expanded_ids: sent.ids,
            expand_all: sent.all,
            skip: params.startRow,
            limit: params.endRow - params.startRow,
        })
            .then((page) => {
                // Hold what the server opened as a list to edit, unless the
                // expansion or filters changed while the request was out
                if (this.expansion === sent && (!sent.ids || sent.all)) {
                    this.expansion = { ids: page.expanded_ids, all: false }
                }
                const rows = page.data.map((r) => this.toRow(r, highlight))
                preloadFlags(rows.map((r) => r.flagUrl))
                params.successCallback(rows, page.count)
            })
            .catch((err) => {
                params.failCallback()
                this.onError(err)
            })
    }
}

export default JurisdictionRowSource
