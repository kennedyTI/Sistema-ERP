import * as React from "react";

type Theme = "light" | "dark";
const ThemeCtx = React.createContext<{ theme: Theme; toggle: () => void } | null>(null);

export function ThemeProvider({
  children,
  forceLight = false,
}: {
  children: React.ReactNode;
  forceLight?: boolean;
}) {
  const [theme, setTheme] = React.useState<Theme>(() => {
    if (typeof window === "undefined") return "light";

    const stored = localStorage.getItem("industria-theme") as Theme | null;
    return stored ?? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  });

  React.useEffect(() => {
    const root = document.documentElement;
    const activeTheme = forceLight ? "light" : theme;
    root.classList.toggle("dark", activeTheme === "dark");

    if (!forceLight) {
      localStorage.setItem("industria-theme", theme);
    }
  }, [forceLight, theme]);

  return (
    <ThemeCtx.Provider value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export function useTheme() {
  const ctx = React.useContext(ThemeCtx);
  if (!ctx) throw new Error("useTheme outside provider");
  return ctx;
}
