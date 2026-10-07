import Autocomplete from "@mui/material/Autocomplete"
import TextField from "@mui/material/TextField"
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

import type { RegionType } from "@/client"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { Facet, FacetOption } from "./filterTree"
import type { JurisdictionMode, StatusFilter } from "./types"

export type ToolbarSummary = {
    shown: number
    total: number
    enabled: number
    // User scope only
    locked?: number
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
    summary,
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
    facets: Facet[]
    onFacetChange: (type: RegionType, ids: string[]) => void
    filtering: boolean
    onClear: () => void
    summary: ToolbarSummary
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
                        <TabsTrigger value="all" className="px-3">
                            <Layers className="text-muted-foreground" />
                            All
                            <span className="text-xs tabular-nums text-muted-foreground">
                                {counts.all}
                            </span>
                        </TabsTrigger>
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
                        {/* For the company the license is its own selection, so
                            nothing is ever off but licensed */}
                        {mode === "user" && (
                            <TabsTrigger
                                value="available"
                                title="Off for you, but included in your company's license"
                                className="group px-3 data-[state=active]:text-primary"
                            >
                                <CirclePlus className="text-muted-foreground group-data-[state=active]:text-primary" />
                                Available
                                <span className="text-xs tabular-nums text-muted-foreground">
                                    {counts.available}
                                </span>
                            </TabsTrigger>
                        )}
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
                    </TabsList>
                </Tabs>
                {facets.map((facet) => (
                    <Autocomplete<FacetOption, true>
                        key={facet.type}
                        multiple
                        size="small"
                        limitTags={2}
                        disableCloseOnSelect
                        className="w-full sm:w-60"
                        options={facet.options}
                        // Wider than the input so long names aren't cut off
                        slotProps={{ popper: { sx: { minWidth: 320 } } }}
                        value={facet.options.filter((o) =>
                            facet.value.includes(o.id),
                        )}
                        onChange={(_, picked) =>
                            onFacetChange(
                                facet.type,
                                picked.map((o) => o.id),
                            )
                        }
                        getOptionLabel={(o) => o.label}
                        getOptionKey={(o) => o.id}
                        isOptionEqualToValue={(a, b) => a.id === b.id}
                        noOptionsText={`No ${facet.label.toLowerCase()} matches`}
                        renderOption={({ key, ...props }, o) => (
                            <li key={key} {...props}>
                                <span className="flex min-w-0 items-center gap-2">
                                    {o.flagUrl ? (
                                        <img
                                            src={o.flagUrl}
                                            alt=""
                                            className="h-3.5 w-5 shrink-0 rounded-[2px] border object-cover"
                                        />
                                    ) : (
                                        <span className="w-5 shrink-0" />
                                    )}
                                    <span className="truncate">{o.label}</span>
                                    {o.context && (
                                        <span className="truncate text-xs opacity-60">
                                            · {o.context}
                                        </span>
                                    )}
                                </span>
                            </li>
                        )}
                        renderInput={(params) => (
                            <TextField
                                {...params}
                                label={facet.label}
                                placeholder={
                                    facet.value.length ? undefined : "Any"
                                }
                            />
                        )}
                    />
                ))}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm text-muted-foreground" aria-live="polite">
                    {filtering ? (
                        <>
                            Showing{" "}
                            <span className="font-medium text-foreground">
                                {summary.shown}
                            </span>{" "}
                            of {summary.total}
                        </>
                    ) : (
                        <>{summary.total} jurisdictions</>
                    )}
                    {" · "}
                    <span className="font-medium text-foreground">
                        {summary.enabled}
                    </span>{" "}
                    enabled
                    {summary.locked != null && summary.locked > 0 && (
                        <> · {summary.locked} not enabled for your company</>
                    )}
                    {" · "}
                    <button
                        type="button"
                        aria-haspopup="dialog"
                        className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
                        onClick={onViewSelection}
                    >
                        <ListChecks className="size-4" />
                        View selection
                    </button>
                </p>
                <div className="flex shrink-0 gap-2">
                    {filtering && (
                        <Button variant="ghost" size="sm" onClick={onClear}>
                            <X />
                            Clear filters
                        </Button>
                    )}
                    <fieldset
                        aria-label="Expand or collapse rows"
                        className="m-0 flex h-8 min-w-0 items-center rounded-lg border bg-muted p-0.5"
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
            </div>
        </div>
    )
}

export default JurisdictionToolbar
