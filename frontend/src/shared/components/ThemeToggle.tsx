import { Sun, Moon } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { useTheme } from "@/shared/lib/theme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const label = theme === "dark" ? "Usar tema claro" : "Usar tema escuro";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      aria-label="Alternar tema"
      title={label}
      className="rounded-full border border-primary/10 bg-card/75 text-primary shadow-sm backdrop-blur hover:bg-primary-soft hover:text-primary-dark dark:border-white/10 dark:bg-white/5 dark:text-primary-foreground dark:hover:bg-primary/15 dark:hover:text-primary"
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}

