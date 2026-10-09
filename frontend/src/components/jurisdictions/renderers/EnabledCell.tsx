import Tooltip from "@mui/material/Tooltip"
import type { ICellRendererParams } from "ag-grid-community"
import { ToggleSwitch } from "@/components/common/ToggleSwitch"
import type {
    JurisdictionGridContext,
    JurisdictionRow,
} from "@/components/jurisdictions/jurisdictionTypes"
import { LockedIcon } from "@/components/jurisdictions/renderers/LockedIcon"

export function EnabledCell({
    data,
    context,
}: ICellRendererParams<JurisdictionRow, unknown, JurisdictionGridContext>) {
    if (!data) return null
    const {
        jurisdiction: j,
        mode,
        checked,
        disabled,
        disabledReason,
        unlock,
        subtree,
    } = data
    // The switch is the row itself; select-all for what's under it has its own
    // column. Structural jurisdictions only group others, so they get no switch.
    if (j.is_structural) return null
    const scope = mode === "company" ? "for the company" : "for me"
    return (
        <div className="flex h-full items-center gap-0.5">
            <Tooltip
                title={
                    disabledReason ? (
                        <span className="flex flex-col gap-1">
                            <span>{disabledReason}</span>
                            {unlock?.kind === "company" && (
                                <span>
                                    Enable license with a{" "}
                                    <a
                                        href="mailto:sales@daptic.com"
                                        className="font-medium underline underline-offset-2"
                                    >
                                        Daptic
                                    </a>{" "}
                                    sales associate.
                                </span>
                            )}
                            {unlock?.kind === "email" && (
                                <a
                                    href={unlock.href}
                                    className="font-medium underline underline-offset-2"
                                >
                                    {unlock.label}
                                </a>
                            )}
                        </span>
                    ) : (
                        ""
                    )
                }
                placement="left"
                enterDelay={150}
                // Time to move onto the tooltip's link
                leaveDelay={unlock ? 200 : 0}
                arrow
            >
                {/* A disabled input gets no pointer or focus events, so the wrapper
                    carries the tooltip and is focusable for keyboard users. An empty
                    title shows no tooltip. */}
                <span tabIndex={disabledReason ? 0 : undefined}>
                    <ToggleSwitch
                        checked={checked}
                        disabled={disabled}
                        label={`Enable ${j.name} ${scope}`}
                        onChange={(on) => context.toggleEnabled(j.id, on)}
                    />
                </span>
            </Tooltip>
            {/* A fully locked subtree shows its lock by select-all instead */}
            {data.locked && subtree?.total !== 0 && <LockedIcon />}
        </div>
    )
}

export default EnabledCell
