import Tooltip from "@mui/material/Tooltip"
import {
    ChevronsDownUp,
    ChevronsUpDown,
    CircleCheck,
    CircleOff,
    CirclePlus,
    Layers,
    ListChecks,
    Search,
    X,
} from "lucide-react"

import type { JurisdictionFacet, RegionType } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FacetFilter } from "./FacetFilter"
import type { JurisdictionMode, StatusFilter } from "./types"

// What each status tab shows, worded for the scope being edited
const statusHints: Record<JurisdictionMode, Record<StatusFilter, string>> = {
    user: {
        all: "Every jurisdiction, whether or not it's on for you.",
        enabled: "On for you. These are the jurisdictions you manage.",
        available:
            "In your company's license but not on for you yet. You can turn these on.",
        disabled: "Not in your company's license, so you can't turn these on.",
    },
    company: {
        all: "Every jurisdiction, whether it's on or off for the company.",
        enabled:
            "Jurisdictions this company has turned on. Members can pick from these.",
        // Never shown: the company's selections are its license
        available: "",
        disabled:
            "Jurisdictions your company hasn't turned on. Members can't pick these.",
    },
}

export function JurisdictionToolbar({
    mode,
    search,
    onSearchChange,
    status,
    counts,
    onStatusChange,
    facets,
    onFacetChange,
    filtering,
    onClear,
    onExpandAll,
    onCollapseAll,
    onViewSelection,
}: {
    mode: JurisdictionMode
    search: string
    onSearchChange: (search: string) => void
    status: StatusFilter
    // Rows each tab would show under the current search and facets
    counts: Record<StatusFilter, number>
    onStatusChange: (status: StatusFilter) => void
    facets: JurisdictionFacet[]
    onFacetChange: (type: RegionType, ids: string[]) => void
    filtering: boolean
    onClear: () => void
    onExpandAll: () => void
    onCollapseAll: () => void
    onViewSelection: () => void
}) {
    return (
        <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2">
                <div className="relative w-full sm:w-64">
                    <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                        type="text"
                        value={search}
                        onChange={(e) => onSearchChange(e.target.value)}
                        placeholder="Search name or code"
                        aria-label="Search jurisdictions"
                        className="h-10 pr-8 pl-8"
                    />
                    {search && (
                        <button
                            type="button"
                            aria-label="Clear search"
                            className="absolute top-1/2 right-2 -translate-y-1/2 rounded p-0.5 text-muted-foreground hover:bg-muted"
                            onClick={() => onSearchChange("")}
                        >
                            <X className="size-4" />
                        </button>
                    )}
                </div>
                <Tabs
                    value={status}
                    onValueChange={(value) =>
                        onStatusChange(value as StatusFilter)
                    }
                >
                    <TabsList
                        aria-label="Filter by status"
                        className="h-10 rounded-lg border p-1"
                    >
                        <Tooltip
                            title={statusHints[mode].all}
                            placement="bottom"
                            enterDelay={1500}
                            arrow
                        >
                            <TabsTrigger value="all" className="px-3">
                                <Layers className="text-muted-foreground" />
                                All
                                <span className="text-xs tabular-nums text-muted-foreground">
                                    {counts.all}
                                </span>
                            </TabsTrigger>
                        </Tooltip>
                        <Tooltip
                            title={statusHints[mode].enabled}
                            placement="bottom"
                            enterDelay={1500}
                            arrow
                        >
                            <TabsTrigger
                                value="enabled"
                                className="group px-3 data-[state=active]:text-primary"
                            >
                                <CircleCheck className="text-muted-foreground group-data-[state=active]:text-primary" />
                                Enabled
                                <span className="text-xs tabular-nums text-muted-foreground">
                                    {counts.enabled}
                                </span>
                            </TabsTrigger>
                        </Tooltip>
                        {/* For the company the license is its own selection, so
                            nothing is ever off but licensed */}
                        {mode === "user" && (
                            <Tooltip
                                title={statusHints[mode].available}
                                placement="bottom"
                                enterDelay={1500}
                                arrow
                            >
                                <TabsTrigger
                                    value="available"
                                    className="group px-3 data-[state=active]:text-primary"
                                >
                                    <CirclePlus className="text-muted-foreground group-data-[state=active]:text-primary" />
                                    Available
                                    <span className="text-xs tabular-nums text-muted-foreground">
                                        {counts.available}
                                    </span>
                                </TabsTrigger>
                            </Tooltip>
                        )}
                        <Tooltip
                            title={statusHints[mode].disabled}
                            placement="bottom"
                            enterDelay={1500}
                            arrow
                        >
                            <TabsTrigger
                                value="disabled"
                                className="group px-3 data-[state=active]:text-destructive"
                            >
                                <CircleOff className="text-muted-foreground group-data-[state=active]:text-destructive" />
                                Disabled
                                <span className="text-xs tabular-nums text-muted-foreground">
                                    {counts.disabled}
                                </span>
                            </TabsTrigger>
                        </Tooltip>
                    </TabsList>
                </Tabs>
                <Button
                    variant="outline"
                    aria-haspopup="dialog"
                    className="h-10"
                    onClick={onViewSelection}
                >
                    <ListChecks />
                    View selection
                </Button>
                <fieldset
                    aria-label="Expand or collapse rows"
                    className="m-0 flex h-10 min-w-0 items-center rounded-lg border bg-muted p-1 sm:ml-auto"
                >
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-full rounded-md px-2.5 text-muted-foreground hover:bg-background hover:text-foreground hover:shadow-sm"
                        onClick={onExpandAll}
                    >
                        <ChevronsUpDown />
                        Expand all
                    </Button>
                    <div className="mx-0.5 h-4 w-px bg-border" />
                    <Button
                        variant="ghost"
                        size="sm"
                        className="h-full rounded-md px-2.5 text-muted-foreground hover:bg-background hover:text-foreground hover:shadow-sm"
                        onClick={onCollapseAll}
                    >
                        <ChevronsDownUp />
                        Collapse all
                    </Button>
                </fieldset>
            </div>
            <div className="flex flex-wrap items-center gap-2">
                {facets.map((facet) => (
                    <FacetFilter
                        key={facet.type}
                        facet={facet}
                        onChange={(ids) => onFacetChange(facet.type, ids)}
                    />
                ))}
                {filtering && (
                    <Button
                        variant="outline"
                        className="h-10"
                        onClick={onClear}
                    >
                        <X />
                        Clear filters
                    </Button>
                )}
            </div>
        </div>
    )
}

export default JurisdictionToolbar
