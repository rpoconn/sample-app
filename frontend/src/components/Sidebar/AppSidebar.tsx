import { Building2, Globe, Users } from "lucide-react"

import { SidebarAppearance } from "@/components/Common/Appearance"
import { Logo } from "@/components/Common/Logo"
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarHeader,
} from "@/components/ui/sidebar"
import useAuth from "@/hooks/useAuth"
import { type Item, Main } from "./Main"
import { User } from "./User"

const baseItems: Item[] = [
    { icon: Globe, title: "Jurisdictions", path: "/jurisdictions" },
]

export function AppSidebar() {
    const { user: currentUser } = useAuth()

    const isCompanyAdmin =
        currentUser?.is_superuser || currentUser?.company_role === "admin"
    const items: Item[] = [
        ...baseItems,
        ...(isCompanyAdmin
            ? [
                  {
                      icon: Building2,
                      title: "Company Admin",
                      path: "/company-admin",
                  },
              ]
            : []),
        ...(currentUser?.is_superuser
            ? [{ icon: Users, title: "Admin", path: "/admin" }]
            : []),
    ]

    return (
        <Sidebar collapsible="icon">
            <SidebarHeader className="px-4 py-6 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:items-center">
                <Logo variant="responsive" />
            </SidebarHeader>
            <SidebarContent>
                <Main items={items} />
            </SidebarContent>
            <SidebarFooter>
                <SidebarAppearance />
                <User user={currentUser} />
            </SidebarFooter>
        </Sidebar>
    )
}

export default AppSidebar
