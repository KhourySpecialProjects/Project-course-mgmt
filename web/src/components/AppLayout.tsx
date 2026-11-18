"use client";

// The frame around every logged-in page: header, sidebar navigation, content.
// Built on Mantine's AppShell: https://mantine.dev/core/app-shell/

import {
  ActionIcon,
  AppShell,
  Avatar,
  Burger,
  Group,
  Menu,
  NavLink,
  ScrollArea,
  Text,
  Title,
  useComputedColorScheme,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconChevronDown,
  IconHome,
  IconKey,
  IconLogout,
  IconMoon,
  IconSchool,
  IconSettings,
  IconSun,
  IconUserCog,
  IconUsers,
} from "@tabler/icons-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/components/AuthProvider";
import { toolModules } from "@/modules/registry";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, { toggle, close }] = useDisclosure();
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  const navItem = (href: string, label: string, Icon: React.ElementType) => (
    <NavLink
      key={href}
      component={Link}
      href={href}
      label={label}
      leftSection={<Icon size={18} stroke={1.5} />}
      active={isActive(href)}
      onClick={close}
    />
  );

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: "sm", collapsed: { mobile: !mobileOpen } }}
      padding="lg"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="sm">
            <Burger opened={mobileOpen} onClick={toggle} hiddenFrom="sm" size="sm" />
            <IconSchool size={26} stroke={1.5} />
            <Title order={4}>Course Workbench</Title>
          </Group>

          <Group gap="xs">
            <ColorSchemeToggle />
            <Menu position="bottom-end" width={220}>
              <Menu.Target>
                <Group gap={6} style={{ cursor: "pointer" }}>
                  <Avatar size="sm" radius="xl" color="indigo">
                    {(user?.full_name || user?.email || "?").charAt(0).toUpperCase()}
                  </Avatar>
                  <Text size="sm" visibleFrom="sm">
                    {user?.full_name || user?.email}
                  </Text>
                  <IconChevronDown size={14} />
                </Group>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>{user?.email}</Menu.Label>
                <Menu.Item component={Link} href="/account" leftSection={<IconUserCog size={16} />}>
                  Account
                </Menu.Item>
                <Menu.Item
                  component={Link}
                  href="/account?tab=api-keys"
                  leftSection={<IconKey size={16} />}
                >
                  My API keys
                </Menu.Item>
                <Menu.Item leftSection={<IconLogout size={16} />} onClick={logout}>
                  Log out
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        <AppShell.Section grow component={ScrollArea}>
          {navItem("/", "Dashboard", IconHome)}

          <Text size="xs" fw={600} c="dimmed" tt="uppercase" px="sm" pt="md" pb={4}>
            Tools
          </Text>
          {toolModules.map((m) => navItem(m.href, m.name, m.icon))}

          {user?.is_superuser && (
            <>
              <Text size="xs" fw={600} c="dimmed" tt="uppercase" px="sm" pt="md" pb={4}>
                Admin
              </Text>
              {navItem("/admin/users", "Users", IconUsers)}
              {navItem("/admin/settings", "System settings", IconSettings)}
            </>
          )}
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}

function ColorSchemeToggle() {
  const { setColorScheme } = useMantineColorScheme();
  const computed = useComputedColorScheme("light", { getInitialValueInEffect: true });
  return (
    <ActionIcon
      variant="default"
      size="lg"
      aria-label="Toggle color scheme"
      onClick={() => setColorScheme(computed === "light" ? "dark" : "light")}
    >
      {computed === "light" ? <IconMoon size={18} /> : <IconSun size={18} />}
    </ActionIcon>
  );
}
