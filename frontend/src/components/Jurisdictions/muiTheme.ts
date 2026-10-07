import { createTheme } from "@mui/material/styles"

// MUI controls otherwise stay light-styled when the app is dark
const base = { typography: { fontFamily: "inherit" } }

export const muiThemes = {
    light: createTheme({ ...base, palette: { mode: "light" } }),
    dark: createTheme({ ...base, palette: { mode: "dark" } }),
}
