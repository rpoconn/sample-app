import {
    createTheme,
    type Theme,
    type ThemeOptions,
} from "@mui/material/styles"

// Draws MUI's Autocomplete like a shadcn control. Colors come from the shadcn
// CSS variables, so they follow the .dark class on their own.
const radius = {
    sm: "calc(var(--radius) - 4px)",
    md: "calc(var(--radius) - 2px)",
    lg: "var(--radius)",
}

// Chips beside the field, drawn like shadcn's secondary badge. Spacing is in px
// strings: sx reads bare numbers as theme spacing and radius units.
export const chipSx = {
    "&.MuiChip-root": {
        height: 24,
        maxWidth: 160,
        borderRadius: radius.sm,
        border: "1px solid var(--border)",
        backgroundColor: "var(--secondary)",
        color: "var(--secondary-foreground)",
        fontSize: 12,
        fontWeight: 500,
    },
    "& .MuiChip-avatar": {
        flexShrink: 0,
        width: 16,
        height: 11,
        margin: "0 -2px 0 6px",
        borderRadius: "2px",
    },
    "& .MuiChip-label": { padding: "0 4px 0 6px" },
    // Keeps its size when the chip shrinks to fit
    "& .MuiChip-deleteIcon": {
        flexShrink: 0,
        width: 14,
        minWidth: 14,
        height: 14,
        margin: "0 4px 0 0",
        borderRadius: "3px",
        color: "var(--muted-foreground)",
        "&:hover": {
            color: "var(--foreground)",
            backgroundColor: "var(--accent)",
        },
    },
}

// Drawn like the shadcn Input beside it: hairline border, soft focus ring
const autocomplete: NonNullable<ThemeOptions["components"]>["MuiAutocomplete"] =
    {
        styleOverrides: {
            root: {
                "& .MuiOutlinedInput-root.MuiInputBase-sizeSmall": {
                    minHeight: 40,
                    paddingTop: 7,
                    paddingBottom: 7,
                    paddingLeft: 10,
                    gap: 4,
                    borderRadius: radius.md,
                    fontSize: 14,
                    color: "var(--foreground)",
                    backgroundColor: "transparent",
                    boxShadow: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
                    transition: "box-shadow 150ms, border-color 150ms",
                    ".dark &": {
                        backgroundColor:
                            "color-mix(in oklab, var(--input) 30%, transparent)",
                    },
                    "& .MuiOutlinedInput-notchedOutline": {
                        borderColor: "var(--input)",
                        transition: "border-color 150ms",
                    },
                    "&:hover .MuiOutlinedInput-notchedOutline": {
                        borderColor:
                            "color-mix(in oklab, var(--ring) 70%, var(--input))",
                    },
                    "&.Mui-focused": {
                        boxShadow:
                            "0 0 0 3px color-mix(in oklab, var(--ring) 50%, transparent)",
                    },
                    "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
                        borderColor: "var(--ring)",
                        borderWidth: 1,
                    },
                    "& .MuiAutocomplete-input": {
                        minWidth: 40,
                        padding: "1px 2px",
                        "&::placeholder": {
                            color: "var(--muted-foreground)",
                            opacity: 1,
                        },
                    },
                },
            },
            endAdornment: { right: 8 },
            popupIndicator: { padding: 4 },
            clearIndicator: { padding: 4 },
            paper: {
                marginTop: 6,
                backgroundImage: "none",
                backgroundColor: "var(--popover)",
                color: "var(--popover-foreground)",
                border: "1px solid var(--border)",
                borderRadius: radius.lg,
                boxShadow:
                    "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
                fontSize: 14,
            },
            listbox: {
                padding: 4,
                maxHeight: 320,
                "& .MuiAutocomplete-option": {
                    minHeight: 34,
                    padding: "6px 8px",
                    borderRadius: radius.sm,
                    fontSize: 14,
                    "&.Mui-focused": { backgroundColor: "var(--accent)" },
                    '&[aria-selected="true"]': {
                        backgroundColor: "transparent",
                    },
                    '&[aria-selected="true"].Mui-focused': {
                        backgroundColor: "var(--accent)",
                    },
                },
            },
            noOptions: {
                padding: "20px 12px",
                fontSize: 14,
                textAlign: "center",
                color: "var(--muted-foreground)",
            },
        },
    }

// Icon buttons inside the field share the muted hover of shadcn's ghost button
const iconButton: NonNullable<ThemeOptions["components"]>["MuiIconButton"] = {
    styleOverrides: {
        root: {
            ".MuiAutocomplete-endAdornment &": {
                borderRadius: radius.sm,
                color: "var(--muted-foreground)",
                "&:hover": {
                    backgroundColor: "var(--accent)",
                    color: "var(--foreground)",
                },
            },
        },
    },
}

// Layered over the surrounding MUI theme (see MuiThemeProvider), so only the
// autocomplete's own subtree picks up these overrides
export const autocompleteTheme = (outer: Theme) =>
    createTheme(outer, {
        components: {
            MuiAutocomplete: autocomplete,
            MuiIconButton: iconButton,
        },
    })
