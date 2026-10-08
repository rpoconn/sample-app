import {
    createTheme,
    type ThemeOptions,
    ThemeProvider,
} from "@mui/material/styles"
import type { ReactNode } from "react"

import { useTheme } from "@/components/ThemeProvider"

// MUI controls otherwise stay light-styled when the app is dark, and use
// Roboto instead of the app font
const base: ThemeOptions = { typography: { fontFamily: "inherit" } }

const themes = {
    light: createTheme({ ...base, palette: { mode: "light" } }),
    dark: createTheme({ ...base, palette: { mode: "dark" } }),
}

// Wrap any tree that renders MUI components so they follow the app's theme
export function MuiThemeProvider({ children }: { children: ReactNode }) {
    const { resolvedTheme } = useTheme()
    return (
        <ThemeProvider
            theme={resolvedTheme === "dark" ? themes.dark : themes.light}
        >
            {children}
        </ThemeProvider>
    )
}

export default MuiThemeProvider
