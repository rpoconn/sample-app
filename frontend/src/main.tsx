import {
    MutationCache,
    QueryCache,
    QueryClient,
    QueryClientProvider,
} from "@tanstack/react-query"
import { createRouter, RouterProvider } from "@tanstack/react-router"
import { AxiosError } from "axios"
import { StrictMode } from "react"
import ReactDOM from "react-dom/client"
import { client } from "./client/client.gen"
import { ThemeProvider } from "./components/ThemeProvider"
import { Toaster } from "./components/ui/Sonner"
import "./index.css"
import { routeTree } from "./routeTree.gen"

client.setConfig({
    baseURL: import.meta.env.VITE_API_URL ?? "",
    auth: () => localStorage.getItem("access_token") || "",
})

const handleApiError = (error: Error) => {
    if (!(error instanceof AxiosError)) {
        return
    }
    const status = error.response?.status
    const code = error.response?.data?.code
    if (
        status === 401 ||
        (status === 403 &&
            (code === "user_inactive" || code === "company_inactive"))
    ) {
        localStorage.removeItem("access_token")
        window.location.href = "/login"
    }
}
const queryClient = new QueryClient({
    queryCache: new QueryCache({
        onError: handleApiError,
    }),
    mutationCache: new MutationCache({
        onError: handleApiError,
    }),
})

const router = createRouter({ routeTree })
declare module "@tanstack/react-router" {
    interface Register {
        router: typeof router
    }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <ThemeProvider defaultTheme="light" storageKey="vite-ui-theme">
            <QueryClientProvider client={queryClient}>
                <RouterProvider router={router} />
                <Toaster richColors closeButton />
            </QueryClientProvider>
        </ThemeProvider>
    </StrictMode>,
)
