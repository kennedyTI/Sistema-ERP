import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "@/modules/auth/authStore";
import { ThemeProvider } from "@/shared/lib/theme";
import { Toaster } from "@/shared/ui/sonner";

export function AppProviders({
  children,
  queryClient,
}: {
  children: React.ReactNode;
  queryClient: QueryClient;
}) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeProvider>
          {children}
          <Toaster richColors position="top-right" />
        </ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
