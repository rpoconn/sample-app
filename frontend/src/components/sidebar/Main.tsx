import { Link as RouterLink, useRouterState } from "@tanstack/react-router"
import type { LucideIcon } from "lucide-react"

import {
    SidebarGroup,
    SidebarGroupContent,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
    useSidebar,
} from "@/components/ui/Sidebar"

export type Item = {
    icon: LucideIcon
    title: string
    path: string
}

interface MainProps {
    items: Item[]
}

export function Main({ items }: MainProps) {
    const { isMobile, setOpenMobile } = useSidebar()
    const router = useRouterState()
    const currentPath = router.location.pathname

    const handleMenuClick = () => {
        if (isMobile) {
            setOpenMobile(false)
        }
    }

    return (
        <SidebarGroup>
            <SidebarGroupContent>
                <SidebarMenu>
                    {items.map((item) => {
                        const isActive = currentPath === item.path

                        return (
                            <SidebarMenuItem key={item.title}>
                                <SidebarMenuButton
                                    tooltip={item.title}
                                    isActive={isActive}
                                    className="data-[active=true]:bg-sidebar-primary data-[active=true]:text-sidebar-primary-foreground data-[active=true]:hover:bg-sidebar-primary/90 data-[active=true]:hover:text-sidebar-primary-foreground"
                                    asChild
                                >
                                    <RouterLink
                                        to={item.path}
                                        onClick={handleMenuClick}
                                    >
                                        <item.icon />
                                        <span>{item.title}</span>
                                    </RouterLink>
                                </SidebarMenuButton>
                            </SidebarMenuItem>
                        )
                    })}
                </SidebarMenu>
            </SidebarGroupContent>
        </SidebarGroup>
    )
}
