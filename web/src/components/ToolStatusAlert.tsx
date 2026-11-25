"use client";

import { Alert, Anchor, Button, Skeleton, Text } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { api } from "@/lib/api";
import { apiKeysPath } from "@/lib/paths";
import type { ToolStatus } from "@/lib/types";

/** Shows whether a tool module is configured, using GET /api/tools/<id>/status. */
export function ToolStatusAlert({ toolId }: { toolId: string }) {
  const { user } = useAuth();
  const [status, setStatus] = useState<ToolStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ToolStatus>(`/tools/${toolId}/status`)
      .then(setStatus)
      .catch((e: Error) => setError(e.message));
  }, [toolId]);

  if (error)
    return (
      <Alert color="red" title="Could not load status">
        {error}
      </Alert>
    );
  if (!status) return <Skeleton h={60} />;

  // Superusers can add shared keys too; everyone else only their own.
  const canAddMissing =
    status.missing_user_credentials.length > 0 ||
    (user?.is_superuser && status.missing_system_credentials.length > 0);

  return status.configured ? (
    <Alert color="teal" icon={<IconCircleCheck />} title="Configured">
      {status.message}{" "}
      <Anchor href="#api-keys" size="sm">
        Change its API keys
      </Anchor>
    </Alert>
  ) : (
    <Alert color="yellow" icon={<IconAlertTriangle />} title="Not configured yet">
      <Text size="sm">{status.message}</Text>
      {canAddMissing && (
        <Button component={Link} href={apiKeysPath(user)} size="xs" mt="sm" variant="white">
          Add API key
        </Button>
      )}
    </Alert>
  );
}
