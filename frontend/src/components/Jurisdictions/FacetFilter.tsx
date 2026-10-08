import Autocomplete from "@mui/material/Autocomplete"
import Chip from "@mui/material/Chip"
import ClickAwayListener from "@mui/material/ClickAwayListener"
import Popper, { type PopperProps } from "@mui/material/Popper"
import TextField from "@mui/material/TextField"
import Tooltip from "@mui/material/Tooltip"
import { Check, ChevronDown, Search, X } from "lucide-react"
import { useState } from "react"

import type { JurisdictionFacet, JurisdictionFacetOption } from "@/client"
import { cn } from "@/lib/utils"
import { flagUrlForKeys } from "./flags"
import { facetChipSx } from "./muiTheme"

// Lists the options right under the search box instead of floating them
function InlinePopper({
    anchorEl,
    disablePortal,
    open,
    ...props
}: PopperProps) {
    return <div {...(props as React.HTMLAttributes<HTMLDivElement>)} />
}

// A field that shows the picks; clicking anywhere on it opens a panel with
// the search box on top, so the chips never compete with the input for room
export function FacetFilter({
    facet,
    onChange,
}: {
    facet: JurisdictionFacet
    onChange: (ids: string[]) => void
}) {
    const [anchor, setAnchor] = useState<HTMLElement | null>(null)
    const picked = facet.options.filter((o) => facet.value.includes(o.id))
    const first = picked[0]
    const firstFlag = first && flagUrlForKeys(first.flag_keys)
    const close = () => {
        anchor?.focus()
        setAnchor(null)
    }

    return (
        <>
            {/* Not a <button>: the chips inside have their own remove buttons */}
            {/* biome-ignore lint/a11y/useSemanticElements: see above */}
            <div
                role="button"
                tabIndex={0}
                aria-label={`${facet.label} filter`}
                aria-haspopup="listbox"
                aria-expanded={!!anchor}
                data-open={!!anchor}
                className={cn(
                    "flex h-10 w-full min-w-0 cursor-pointer items-center gap-1 rounded-md border border-input bg-transparent pr-1.5 pl-2.5 text-sm shadow-xs outline-none transition-[color,box-shadow] select-none sm:w-72 dark:bg-input/30",
                    "hover:border-ring/70 focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50",
                    "data-[open=true]:border-ring data-[open=true]:ring-[3px] data-[open=true]:ring-ring/50",
                )}
                onClick={(e) => setAnchor(anchor ? null : e.currentTarget)}
                onKeyDown={(e) => {
                    if (
                        e.key === "Enter" ||
                        e.key === " " ||
                        e.key === "ArrowDown"
                    ) {
                        e.preventDefault()
                        setAnchor(e.currentTarget)
                    }
                }}
            >
                <span className="shrink-0 pr-1 text-muted-foreground">
                    {facet.label}
                </span>
                {first ? (
                    <Chip
                        size="small"
                        label={first.label}
                        sx={facetChipSx}
                        className="min-w-0"
                        avatar={
                            firstFlag ? (
                                <img
                                    src={firstFlag}
                                    alt=""
                                    className="object-cover"
                                />
                            ) : undefined
                        }
                        deleteIcon={<X aria-label={`Remove ${first.label}`} />}
                        onDelete={() =>
                            onChange(
                                facet.value.filter((id) => id !== first.id),
                            )
                        }
                        // Removing a pick shouldn't also open the panel
                        onClick={(e) => e.stopPropagation()}
                    />
                ) : (
                    // No pick means no filter: show that as a value, not a hint
                    <Chip size="small" label="Any" sx={facetChipSx} />
                )}
                {picked.length > 1 && (
                    <Tooltip
                        title={picked
                            .slice(1)
                            .map((o) => o.label)
                            .join(", ")}
                        placement="bottom"
                        arrow
                    >
                        <Chip
                            size="small"
                            label={`+${picked.length - 1}`}
                            sx={facetChipSx}
                            className="shrink-0"
                        />
                    </Tooltip>
                )}
                <span className="ml-auto flex shrink-0 items-center">
                    {picked.length > 0 && (
                        <button
                            type="button"
                            aria-label={`Clear ${facet.label.toLowerCase()}`}
                            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                            onClick={(e) => {
                                e.stopPropagation()
                                onChange([])
                            }}
                        >
                            <X className="size-4" />
                        </button>
                    )}
                    <ChevronDown
                        className={cn(
                            "m-1 size-4 text-muted-foreground transition-transform",
                            anchor && "rotate-180",
                        )}
                    />
                </span>
            </div>
            <Popper
                open={!!anchor}
                anchorEl={anchor}
                placement="bottom-start"
                className="z-50"
            >
                <ClickAwayListener
                    // Clicks on the field toggle it themselves
                    onClickAway={(e) => {
                        if (!anchor?.contains(e.target as Node)) close()
                    }}
                >
                    <div className="mt-1.5 w-80 overflow-hidden rounded-lg border bg-popover text-popover-foreground shadow-lg">
                        <Autocomplete<JurisdictionFacetOption, true, true>
                            open
                            multiple
                            disableClearable
                            disableCloseOnSelect
                            autoHighlight
                            forcePopupIcon={false}
                            size="small"
                            options={facet.options}
                            value={picked}
                            onChange={(_, next) =>
                                onChange(next.map((o) => o.id))
                            }
                            onClose={(_, reason) => {
                                if (reason === "escape") close()
                            }}
                            onKeyDown={(e) => {
                                // Backspace edits the search, never the picks
                                if (e.key === "Backspace") {
                                    e.defaultMuiPrevented = true
                                }
                            }}
                            renderValue={() => null}
                            getOptionLabel={(o) => o.label}
                            getOptionKey={(o) => o.id}
                            isOptionEqualToValue={(a, b) => a.id === b.id}
                            noOptionsText={`No ${facet.label.toLowerCase()} matches`}
                            slots={{ popper: InlinePopper }}
                            slotProps={{
                                paper: {
                                    sx: {
                                        m: 0,
                                        border: 0,
                                        borderRadius: 0,
                                        boxShadow: "none",
                                    },
                                },
                            }}
                            renderOption={(
                                { key, ...props },
                                o,
                                { selected },
                            ) => (
                                <li key={key} {...props}>
                                    <span className="flex w-full min-w-0 items-center gap-2.5">
                                        {flagUrlForKeys(o.flag_keys) ? (
                                            <img
                                                src={flagUrlForKeys(
                                                    o.flag_keys,
                                                )}
                                                alt=""
                                                className="h-3.5 w-5 shrink-0 rounded-[2px] object-cover shadow-[0_0_0_1px_var(--border)]"
                                            />
                                        ) : (
                                            <span className="w-5 shrink-0" />
                                        )}
                                        <span className="truncate">
                                            {o.label}
                                        </span>
                                        {o.context && (
                                            <span className="truncate text-xs text-muted-foreground">
                                                {o.context}
                                            </span>
                                        )}
                                        <Check
                                            className={`ml-auto size-4 shrink-0 text-primary ${selected ? "" : "invisible"}`}
                                        />
                                    </span>
                                </li>
                            )}
                            renderInput={(params) => (
                                <div className="border-b p-2">
                                    <TextField
                                        {...params}
                                        autoFocus
                                        placeholder={`Search ${facet.label.toLowerCase()}`}
                                        slotProps={{
                                            ...params.slotProps,
                                            input: {
                                                ...params.slotProps.input,
                                                startAdornment: (
                                                    <Search className="size-4 shrink-0 text-muted-foreground" />
                                                ),
                                            },
                                            htmlInput: {
                                                ...params.slotProps.htmlInput,
                                                "aria-label": `Search ${facet.label.toLowerCase()}`,
                                            },
                                        }}
                                    />
                                </div>
                            )}
                        />
                    </div>
                </ClickAwayListener>
            </Popper>
        </>
    )
}

export default FacetFilter
