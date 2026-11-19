import { Center, Paper, Stack, Text, Title } from "@mantine/core";
import { IconSchool } from "@tabler/icons-react";

/** The centered card used by the sign-in and invite pages. */
export function AuthCard({ subtitle, children }: { subtitle: string; children: React.ReactNode }) {
  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" w="100%" maw={420}>
        <Stack>
          <Stack gap={4} align="center">
            <IconSchool size={40} stroke={1.5} />
            <Title order={3}>Course Workbench</Title>
            <Text size="sm" c="dimmed" ta="center">
              {subtitle}
            </Text>
          </Stack>
          {children}
        </Stack>
      </Paper>
    </Center>
  );
}
