import type { CSSProperties, ReactNode } from "react";

export type WorkspaceIconName = "settings" | "flow" | "export" | "import" | "clock";

const paths: Record<WorkspaceIconName, ReactNode> = {
  settings: <><path d="M3 5h18M3 12h18M3 19h18" /><circle cx="8" cy="5" r="2" /><circle cx="16" cy="12" r="2" /><circle cx="10" cy="19" r="2" /></>,
  flow: <><rect x="8" y="3" width="8" height="5" rx="1.5" /><rect x="8" y="16" width="8" height="5" rx="1.5" /><path d="M12 8v8m-3-3 3 3 3-3" /></>,
  export: <><path d="M12 3v12m-4-4 4 4 4-4M4 16v4h16v-4" /></>,
  import: <><path d="M12 16V4m-4 4 4-4 4 4M4 17v3h16v-3" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
};

/** Decorative only: visible Korean text remains each control's accessible name. */
export function WorkspaceIcon({ name, className, style }: {
  name: WorkspaceIconName; className?: string; style?: CSSProperties;
}) {
  return <svg className={className} style={style} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{paths[name]}</svg>;
}
