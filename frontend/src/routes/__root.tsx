import { createRootRoute, HeadContent, Outlet } from "@tanstack/react-router"
import ErrorComponent from "@/components/common/ErrorComponent"
import NotFound from "@/components/common/NotFound"

export const Route = createRootRoute({
    component: () => (
        <>
            <HeadContent />
            <Outlet />
        </>
    ),
    notFoundComponent: () => <NotFound />,
    errorComponent: () => <ErrorComponent />,
})
