import { createFileRoute, Outlet, redirect } from "@tanstack/react-router"
import { LogOut } from "lucide-react"

import { UsersService } from "@/client"
import { Footer } from "@/components/common/Footer"
import AppSidebar from "@/components/sidebar/AppSidebar"
import { Button } from "@/components/ui/Button"
import {
    SidebarInset,
    SidebarProvider,
    SidebarTrigger,
} from "@/components/ui/Sidebar"
import useAuth, { isAuthError, isLoggedIn } from "@/hooks/useAuth"

export const Route = createFileRoute("/_layout")({
    component: Layout,
    beforeLoad: async ({ context }) => {
        if (!isLoggedIn()) {
            throw redirect({
                to: "/login",
            })
        }
        // A stored token can be stale (e.g. after a database reset), so confirm
        // it before rendering the app; the user is cached for useAuth
        if (context.queryClient.getQueryData(["currentUser"])) {
            return
        }
        try {
            const { data: user } = await UsersService.readUserMe()
            context.queryClient.setQueryData(["currentUser"], user)
        } catch (error) {
            if (!isAuthError(error)) {
                throw error
            }
            localStorage.removeItem("access_token")
            throw redirect({
                to: "/login",
            })
        }
    },
})

function Layout() {
    const { logout } = useAuth()

    return (
        <SidebarProvider>
            <AppSidebar />
            <SidebarInset>
                <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-2 border-b bg-background px-4">
                    <SidebarTrigger className="-ml-1 text-muted-foreground" />
                    <Button
                        variant="ghost"
                        size="sm"
                        className="ml-auto"
                        onClick={logout}
                        data-testid="header-logout"
                    >
                        <LogOut />
                        Log out
                    </Button>
                </header>
                <main className="flex-1 p-6 md:p-8">
                    <div className="mx-auto max-w-7xl">
                        <Outlet />
                    </div>
                </main>
                <Footer />
            </SidebarInset>
        </SidebarProvider>
    )
}
