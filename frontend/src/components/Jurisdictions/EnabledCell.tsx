import Switch from "@mui/material/Switch"
import Tooltip from "@mui/material/Tooltip"
import type { ICellRendererParams } from "ag-grid-community"

import type { JurisdictionGridContext, JurisdictionRow } from "./types"

export function EnabledCell({
    data,
    context,
}: ICellRendererParams<JurisdictionRow, unknown, JurisdictionGridContext>) {
    // Structural jurisdictions only group others; they can't be opted into
    if (!data || data.jurisdiction.is_structural) return null
    const { jurisdiction: j, checked, disabled, disabledReason } = data
    const control = (
        <Switch
            size="small"
            checked={checked}
            disabled={disabled}
            onChange={(e) => context.toggleEnabled(j.id, e.target.checked)}
            slotProps={{ input: { "aria-label": `Enable ${j.name}` } }}
        />
    )
    if (!disabledReason) return control
    return (
        <Tooltip title={disabledReason}>
            <span>{control}</span>
        </Tooltip>
    )
}

export default EnabledCell
