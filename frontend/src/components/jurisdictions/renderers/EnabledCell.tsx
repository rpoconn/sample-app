import Tooltip from "@mui/material/Tooltip"
import type { ICellRendererParams } from "ag-grid-community"
import { TriStateSwitch } from "@/components/common/triStateSwitch/TriStateSwitch"
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
    // Structural jurisdictions only group others; they can't be opted into
    // themselves, but their select-all still covers what's under them
    if (j.is_structural && !subtree) return null
    const scope = mode === "company" ? "for the company" : "for me"
    // Everything the user is allowed to pick is on; a click then turns it off
    const allAvailable =
        !!subtree && subtree.total > 0 && subtree.enabled === subtree.total
    const locked = subtree?.locked ?? 0
    // Fully on only when nothing is held back by the license
    const all = allAvailable && locked === 0
    const some = !!subtree && subtree.enabled > 0 && !all
    const grand = (subtree?.total ?? 0) + locked
    const lockedNote =
        locked > 0
            ? `${locked} of ${grand} in ${j.name} ${locked === 1 ? "isn't" : "aren't"} enabled for your company's license.`
            : ""
    // Non-admins can't change company selections; nothing selectable means
    // everything under the row is locked for the user
    const subtreeDisabled =
        !subtree || subtree.total === 0 || (mode === "company" && disabled)
    const subtreeLabel = subtree
        ? `Enable all of ${j.name} ${scope} (${subtree.enabled} of ${grand} on)`
        : ""
    return (
        <div className="flex h-full items-center gap-1">
            {!j.is_structural && (
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
                        <TriStateSwitch
                            state={checked ? "on" : "off"}
                            disabled={disabled}
                            label={`Enable ${j.name} ${scope}`}
                            onChange={(on) => context.toggleEnabled(j.id, on)}
                        />
                    </span>
                </Tooltip>
            )}
            {/* A fully locked subtree shows its own lock after the select-all */}
            {!j.is_structural && data.locked && subtree?.total !== 0 && (
                <LockedIcon />
            )}
            {subtree && (
                <Tooltip
                    title={
                        subtree.total === 0 ? (
                            `Nothing in ${j.name} is enabled for your license`
                        ) : (
                            <span className="flex flex-col gap-1">
                                <span>
                                    {allAvailable
                                        ? locked > 0
                                            ? `Everything available in ${j.name} is on. Click to turn it off.`
                                            : `Turn off everything in ${j.name}`
                                        : locked > 0
                                          ? `Turn on everything available in ${j.name}`
                                          : `Turn on everything in ${j.name}`}
                                </span>
                                {lockedNote && <span>{lockedNote}</span>}
                            </span>
                        )
                    }
                    placement="left"
                    enterDelay={300}
                    arrow
                >
                    <span className="flex items-center">
                        <TriStateSwitch
                            state={all ? "on" : some ? "mixed" : "off"}
                            disabled={subtreeDisabled}
                            label={subtreeLabel}
                            // Shows mixed when the license holds some back, but
                            // still turns off once everything available is on
                            onChange={() =>
                                context.toggleSubtree(j.id, !allAvailable)
                            }
                        />
                        {subtree.total > 0 && (
                            <span className="text-xs tabular-nums text-muted-foreground">
                                {all
                                    ? "All"
                                    : some
                                      ? `${subtree.enabled} / ${grand}`
                                      : "None"}
                            </span>
                        )}
                    </span>
                </Tooltip>
            )}
            {/* Nothing under the row can be enabled, so a count says nothing */}
            {subtree?.total === 0 && <LockedIcon />}
        </div>
    )
}

export default EnabledCell
