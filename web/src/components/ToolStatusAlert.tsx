"use client";

import { Alert, Button, Skeleton, Text } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck } from "@tabler/icons-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ToolStatus } from "@/lib/types";

/** Shows whether a tool module is configured, using GET /api/tools/<id>/status. */
export function ToolStatusAlert({ toolId }: { toolId: string }) {
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

  return status.configured ? (
    <Alert color="teal" icon={<IconCircleCheck />} title="Configured">
      {status.message}
    </Alert>
  ) : (
    <Alert color="yellow" icon={<IconAlertTriangle />} title="Not configured yet">
      <Text size="sm">{status.message}</Text>
      {status.missing_user_credentials.length > 0 && (
        <Button component={Link} href="/account?tab=api-keys" size="xs" mt="sm" variant="white">
          Add API key
        </Button>
      )}
    </Alert>
  );
}
