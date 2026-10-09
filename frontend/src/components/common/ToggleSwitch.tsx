import Switch from "@mui/material/Switch"
import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

// App colors rather than MUI's palette, so it matches the rest of the UI. "&&&"
// repeats the root class to outrank MUI's checked/disabled rules.
export function ToggleSwitch({
    checked,
    disabled,
    label,
    onChange,
}: {
    checked: boolean
    disabled?: boolean
    label: string
    onChange: (checked: boolean) => void
}) {
    // The knob shows a check when on
    const thumb = (
        <span
            className={cn(
                "flex size-4 items-center justify-center rounded-full bg-white shadow-sm ring-1 ring-black/10 transition-colors",
                checked && "text-primary",
            )}
        >
            {checked && <Check className="size-3" strokeWidth={3.5} />}
        </span>
    )
    return (
        <Switch
            size="small"
            checked={checked}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
            icon={thumb}
            checkedIcon={thumb}
            sx={{
                opacity: disabled ? 0.45 : 1,
                "&&& .MuiSwitch-switchBase + .MuiSwitch-track": {
                    backgroundColor: checked
                        ? "var(--primary)"
                        : "color-mix(in oklch, var(--muted-foreground) 45%, transparent)",
                    opacity: 1,
                },
            }}
            slotProps={{ input: { "aria-label": label } }}
        />
    )
}

export default ToggleSwitch
