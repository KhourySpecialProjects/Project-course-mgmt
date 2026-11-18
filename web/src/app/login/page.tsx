"use client";

import {
  Alert,
  Button,
  Center,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { IconAlertCircle, IconSchool } from "@tabler/icons-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { FullPageLoader } from "@/components/FullPageLoader";

export default function LoginPage() {
  // useSearchParams() must be inside a <Suspense> boundary.
  return (
    <Suspense fallback={<FullPageLoader />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const { user, login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Only allow redirecting to paths on this site (never to another domain).
  const nextParam = searchParams.get("next");
  const next = nextParam?.startsWith("/") && !nextParam.startsWith("//") ? nextParam : "/";

  const form = useForm({
    initialValues: { email: "", password: "" },
    validate: {
      email: (v) => (/^\S+@\S+$/.test(v) ? null : "Enter a valid email"),
      password: (v) => (v.length > 0 ? null : "Enter your password"),
    },
  });

  // Already logged in? Skip the form.
  useEffect(() => {
    if (user) router.replace(next);
  }, [user, next, router]);

  async function handleSubmit(values: typeof form.values) {
    setError(null);
    setSubmitting(true);
    try {
      await login(values.email, values.password);
      // The effect above redirects once `user` is set.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  if (user === undefined || user) return <FullPageLoader />;

  return (
    <Center mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" w="100%" maw={400}>
        <form onSubmit={form.onSubmit(handleSubmit)}>
          <Stack>
            <Stack gap={4} align="center">
              <IconSchool size={40} stroke={1.5} />
              <Title order={3}>Course Workbench</Title>
              <Text size="sm" c="dimmed">
                Sign in to continue
              </Text>
            </Stack>

            {error && (
              <Alert color="red" icon={<IconAlertCircle />}>
                {error}
              </Alert>
            )}

            <TextInput
              label="Email"
              type="email"
              autoComplete="email"
              required
              {...form.getInputProps("email")}
            />
            <PasswordInput
              label="Password"
              autoComplete="current-password"
              required
              {...form.getInputProps("password")}
            />
            <Button type="submit" loading={submitting} fullWidth mt="sm">
              Sign in
            </Button>
          </Stack>
        </form>
      </Paper>
    </Center>
  );
}
