// Root layout: wraps every page in the app. Sets up Mantine (UI components),
// notifications (toasts), and the AuthProvider (who is logged in).

import "@mantine/core/styles.css";
import "@mantine/notifications/styles.css";

import { ColorSchemeScript, MantineProvider, mantineHtmlProps } from "@mantine/core";
import { Notifications } from "@mantine/notifications";
import type { Metadata } from "next";

import { AuthProvider } from "@/components/AuthProvider";
import { theme } from "@/theme";

export const metadata: Metadata = {
  title: "Course Workbench",
  description: "Set up and monitor project-based courses across GitHub and Linear.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" {...mantineHtmlProps}>
      <head>
        {/* Applies light/dark mode before the page paints, to avoid a flash. */}
        <ColorSchemeScript defaultColorScheme="auto" />
      </head>
      <body>
        <MantineProvider theme={theme} defaultColorScheme="auto">
          <Notifications position="top-right" />
          <AuthProvider>{children}</AuthProvider>
        </MantineProvider>
      </body>
    </html>
  );
}
