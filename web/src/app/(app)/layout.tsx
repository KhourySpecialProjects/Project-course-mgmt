"use client";

// Layout for every page inside the (app) folder. The parentheses mean the
// folder name is NOT part of the URL: (app)/account/page.tsx is served at /account.
//
// It does two things:
//   1. Sends logged-out visitors to /login.
//   2. Wraps the page in the AppLayout (header + sidebar).

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppLayout } from "@/components/AppLayout";
import { useAuth } from "@/components/AuthProvider";
import { FullPageLoader } from "@/components/FullPageLoader";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (user === null) {
      const next = encodeURIComponent(window.location.pathname);
      router.replace(`/login?next=${next}`);
    }
  }, [user, router]);

  if (!user) return <FullPageLoader />;
  return <AppLayout>{children}</AppLayout>;
}
