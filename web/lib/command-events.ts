export type CommandBarMode = "command" | "project-switcher";

export interface CommandBarOpenRequestDetail {
  mode?: CommandBarMode;
  query?: string;
}

export interface CommandBarStateDetail {
  activeCommandId: string | null;
  loading: boolean;
  mode: CommandBarMode;
  open: boolean;
  query: string;
  resultCount: number;
}

export const COMMAND_BAR_OPEN_REQUEST_EVENT = "ukde-command-bar-open-request";
export const COMMAND_BAR_STATE_EVENT = "ukde-command-bar-state";
