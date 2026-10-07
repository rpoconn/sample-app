import Switch from "@mui/material/Switch"

import { type SwitchState, SwitchThumb } from "./SwitchThumb"

export type { SwitchState } from "./SwitchThumb"

// Small switch travel; "mixed" parks the knob halfway
const offset: Record<SwitchState, number> = { on: 16, mixed: 8, off: 0 }

// App colors rather than MUI's palette, so it matches the rest of the UI
const track: Record<SwitchState, string> = {
    on: "var(--primary)",
    mixed: "color-mix(in oklch, var(--primary) 45%, transparent)",
    off: "color-mix(in oklch, var(--muted-foreground) 45%, transparent)",
}

// MUI's Switch has no indeterminate state, so this draws all three itself. "&&&"
// repeats the root class to outrank MUI's checked/disabled rules.
export function TriStateSwitch({
    state,
    disabled,
    label,
    onChange,
}: {
    state: SwitchState
    disabled?: boolean
    label: string
    // Mixed or off turns on; on turns off
    onChange: (on: boolean) => void
}) {
    return (
        <Switch
            size="small"
            checked={state === "on"}
            disabled={disabled}
            onChange={() => onChange(state !== "on")}
            icon={<SwitchThumb state={state} />}
            checkedIcon={<SwitchThumb state={state} />}
            sx={{
                opacity: disabled ? 0.45 : 1,
                "&&& .MuiSwitch-switchBase": {
                    transform: `translateX(${offset[state]}px)`,
                },
                "&&& .MuiSwitch-switchBase + .MuiSwitch-track": {
                    backgroundColor: track[state],
                    opacity: 1,
                },
            }}
            slotProps={{ input: { "aria-label": label } }}
        />
    )
}

export default TriStateSwitch
