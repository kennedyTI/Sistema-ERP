import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AuthProvider } from "@/modules/auth/authStore";
import { ThemeProvider } from "@/shared/lib/theme";

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
        <ThemeProvider>{children}</ThemeProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}
