import type { QueryClient } from "@tanstack/react-query"
import {
    createRootRouteWithContext,
    HeadContent,
    Outlet,
} from "@tanstack/react-router"
import ErrorComponent from "@/components/common/ErrorComponent"
import NotFound from "@/components/common/NotFound"

type RouterContext = {
    queryClient: QueryClient
}

export const Route = createRootRouteWithContext<RouterContext>()({
    component: () => (
        <>
            <HeadContent />
            <Outlet />
        </>
    ),
    notFoundComponent: () => <NotFound />,
    errorComponent: () => <ErrorComponent />,
})
