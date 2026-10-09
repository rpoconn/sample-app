import type {
    JurisdictionGridRow,
    RegionType,
    SubtreeSelection,
} from "@/client"

export type JurisdictionMode = "company" | "user"

// Column ids double as the API's sort_by values
export type JurisdictionSort = {
    sort_by: "name" | "enabled"
    sort_dir: "asc" | "desc"
}

// Selected jurisdiction ids per region type; each type narrows to their subtrees
export type TypeFilters = Partial<Record<RegionType, string[]>>

// Whether a row is on in the current scope. Available (user scope only) is off
// but covered by the company's license. Disabled is locked: the company hasn't
// turned it on, so it can't be on for anyone.
export type StatusFilter = "all" | "enabled" | "available" | "disabled"

// Sent to the server, which does the filtering
export type JurisdictionFilters = {
    search: string
    byType: TypeFilters
    status: StatusFilter
}

// How a locked row can get turned on for the company, shown in its tooltip
export type Unlock =
    // Admins: contact Daptic sales to license it
    | { kind: "company" }
    // Members: email the company's admins
    | { kind: "email"; href: string; label: string }

export type JurisdictionRow = {
    // The server's row: the jurisdiction and its state under the current filters
    jurisdiction: JurisdictionGridRow
    mode: JurisdictionMode
    // Indent level as shown; less than the tree depth when a filter hides ancestors
    depth: number
    flagUrl?: string
    expanded: boolean
    // Whether expanding would show anything under the current filters
    hasChildren: boolean
    checked: boolean
    disabled: boolean
    disabledReason?: string
    // User scope: the company hasn't opted in, so the row can't be enabled
    locked: boolean
    unlock?: Unlock
    // Search term to highlight in the name
    highlight?: string
    // Company scope (admins): users who opted into this jurisdiction
    userCount?: number
    // Rows with children: selectable jurisdictions in the subtree (self included),
    // and how many of them are on. Drives the select-all button.
    subtree?: SubtreeSelection
}

export type JurisdictionGridContext = {
    toggleExpanded: (id: string) => void
    toggleEnabled: (id: string, enabled: boolean) => void
    // Turns the row and everything under it on or off in one save
    toggleSubtree: (id: string, enabled: boolean) => void
}
