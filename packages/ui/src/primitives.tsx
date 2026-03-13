"use client";

import {
  createContext,
  type KeyboardEvent,
  type MutableRefObject,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState
} from "react";
import { createPortal } from "react-dom";

import {
  type SortDirection,
  findFirstEnabledIndex,
  resolveToolbarTargetIndex,
  stableSortRows
} from "./primitives-logic";

export type PrimitiveTone =
  | "neutral"
  | "success"
  | "warning"
  | "danger"
  | "info";

interface ClassNameProps {
  className?: string;
}

function cx(...tokens: Array<string | false | undefined>): string {
  return tokens.filter(Boolean).join(" ");
}

function resolveFocusableElements(target: HTMLElement): HTMLElement[] {
  return Array.from(
    target.querySelectorAll<HTMLElement>(
      [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        "[tabindex]:not([tabindex='-1'])"
      ].join(",")
    )
  ).filter((element) => {
    return !(
      element.hasAttribute("hidden") ||
      element.getAttribute("aria-hidden") === "true"
    );
  });
}

let scrollLockCount = 0;

function lockBodyScroll(): void {
  scrollLockCount += 1;
  if (scrollLockCount === 1) {
    document.body.classList.add("ukde-scroll-locked");
  }
}

function unlockBodyScroll(): void {
  scrollLockCount = Math.max(0, scrollLockCount - 1);
  if (scrollLockCount === 0) {
    document.body.classList.remove("ukde-scroll-locked");
  }
}

const layerStack: string[] = [];

function registerLayer(layerId: string): () => void {
  layerStack.push(layerId);
  return () => {
    const index = layerStack.lastIndexOf(layerId);
    if (index >= 0) {
      layerStack.splice(index, 1);
    }
  };
}

function isTopLayer(layerId: string): boolean {
  return layerStack[layerStack.length - 1] === layerId;
}

interface LayerInteractionOptions {
  closeOnEscape?: boolean;
  closeOnOutsideClick?: boolean;
  lockScroll?: boolean;
  onClose: () => void;
  open: boolean;
  returnFocusRef?: MutableRefObject<HTMLElement | null>;
  trapFocus?: boolean;
}

function useLayerInteraction({
  closeOnEscape = true,
  closeOnOutsideClick = true,
  lockScroll = false,
  onClose,
  open,
  returnFocusRef,
  trapFocus = false
}: LayerInteractionOptions): MutableRefObject<HTMLDivElement | null> {
  const layerRef = useRef<HTMLDivElement | null>(null);
  const layerId = useId();
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) {
      return;
    }
    const layerElement = layerRef.current;
    if (!layerElement) {
      return;
    }

    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const unregister = registerLayer(layerId);

    if (lockScroll) {
      lockBodyScroll();
    }

    const focusableElements = resolveFocusableElements(layerElement);
    const initialTarget = focusableElements[0] ?? layerElement;
    initialTarget.focus({ preventScroll: true });

    const handleKeyDown = (event: KeyboardEvent | globalThis.KeyboardEvent) => {
      if (!isTopLayer(layerId)) {
        return;
      }
      if (event.key === "Escape" && closeOnEscape) {
        event.preventDefault();
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !trapFocus) {
        return;
      }
      const focusables = resolveFocusableElements(layerElement);
      if (focusables.length === 0) {
        event.preventDefault();
        layerElement.focus({ preventScroll: true });
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus({ preventScroll: true });
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus({ preventScroll: true });
      }
    };

    const handlePointerDown = (event: PointerEvent) => {
      if (!isTopLayer(layerId) || !closeOnOutsideClick) {
        return;
      }
      const target = event.target as Node | null;
      if (!target) {
        return;
      }
      if (!layerElement.contains(target)) {
        onCloseRef.current();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handlePointerDown, true);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handlePointerDown, true);
      unregister();
      if (lockScroll) {
        unlockBodyScroll();
      }
      const explicitReturn = returnFocusRef?.current ?? null;
      if (explicitReturn) {
        explicitReturn.focus({ preventScroll: true });
      } else if (previouslyFocused?.isConnected) {
        previouslyFocused.focus({ preventScroll: true });
      }
    };
  }, [
    closeOnEscape,
    closeOnOutsideClick,
    layerId,
    lockScroll,
    open,
    returnFocusRef,
    trapFocus
  ]);

  return layerRef;
}

function resolveOverlayRoot(): HTMLElement {
  const existing = document.getElementById("ukde-overlay-root");
  if (existing) {
    return existing;
  }
  const root = document.createElement("div");
  root.id = "ukde-overlay-root";
  root.className = "ukde-overlay-root";
  document.body.appendChild(root);
  return root;
}

function OverlayPortal({ children }: { children: ReactNode }) {
  const [root, setRoot] = useState<HTMLElement | null>(null);

  useEffect(() => {
    setRoot(resolveOverlayRoot());
  }, []);

  if (!root) {
    return null;
  }
  return createPortal(children, root);
}

export interface StatusChipProps extends ClassNameProps {
  children: ReactNode;
  tone?: PrimitiveTone;
}

export function StatusChip({
  children,
  className,
  tone = "neutral"
}: StatusChipProps) {
  return (
    <span className={cx("ukde-status-chip", className)} data-tone={tone}>
      {children}
    </span>
  );
}

export interface InlineAlertProps extends ClassNameProps {
  actions?: ReactNode;
  children?: ReactNode;
  title: string;
  tone?: PrimitiveTone;
}

export function InlineAlert({
  actions,
  children,
  className,
  title,
  tone = "info"
}: InlineAlertProps) {
  const role = tone === "danger" || tone === "warning" ? "alert" : "status";
  return (
    <section
      className={cx("ukde-inline-alert", className)}
      data-tone={tone}
      role={role}
    >
      <div className="ukde-inline-alert-head">
        <strong>{title}</strong>
      </div>
      {children ? <p>{children}</p> : null}
      {actions ? (
        <div className="ukde-inline-alert-actions">{actions}</div>
      ) : null}
    </section>
  );
}

export function BannerAlert(props: InlineAlertProps) {
  return (
    <InlineAlert
      {...props}
      className={cx("ukde-banner-alert", props.className)}
    />
  );
}

export interface BreadcrumbItem {
  href?: string;
  label: string;
}

export interface BreadcrumbsProps extends ClassNameProps {
  ariaLabel?: string;
  items: BreadcrumbItem[];
}

export function Breadcrumbs({
  ariaLabel = "Breadcrumb",
  className,
  items
}: BreadcrumbsProps) {
  if (items.length === 0) {
    return null;
  }
  return (
    <nav aria-label={ariaLabel} className={cx("ukde-breadcrumbs", className)}>
      <ol>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`}>
              {isLast ? (
                <span aria-current="page">{item.label}</span>
              ) : item.href ? (
                <a href={item.href}>{item.label}</a>
              ) : (
                <span>{item.label}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export interface ModalDialogProps extends ClassNameProps {
  children: ReactNode;
  closeLabel?: string;
  description?: string;
  footer?: ReactNode;
  onClose: () => void;
  open: boolean;
  title: string;
}

export function ModalDialog({
  children,
  className,
  closeLabel = "Close dialog",
  description,
  footer,
  onClose,
  open,
  title
}: ModalDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const layerRef = useLayerInteraction({
    lockScroll: true,
    onClose,
    open,
    trapFocus: true
  });

  if (!open) {
    return null;
  }

  return (
    <OverlayPortal>
      <div className="ukde-overlay-scrim">
        <div
          aria-describedby={description ? descriptionId : undefined}
          aria-labelledby={titleId}
          aria-modal="true"
          className={cx("ukde-dialog", className)}
          ref={layerRef}
          role="dialog"
          tabIndex={-1}
        >
          <header className="ukde-dialog-head">
            <h2 id={titleId}>{title}</h2>
            <button
              aria-label={closeLabel}
              className="ukde-overlay-close"
              onClick={onClose}
              type="button"
            >
              Close
            </button>
          </header>
          {description ? (
            <p className="ukde-muted" id={descriptionId}>
              {description}
            </p>
          ) : null}
          <div className="ukde-dialog-body">{children}</div>
          {footer ? (
            <footer className="ukde-dialog-footer">{footer}</footer>
          ) : null}
        </div>
      </div>
    </OverlayPortal>
  );
}

export interface DrawerProps extends ClassNameProps {
  children: ReactNode;
  closeLabel?: string;
  description?: string;
  onClose: () => void;
  open: boolean;
  side?: "left" | "right";
  title: string;
}

export function Drawer({
  children,
  className,
  closeLabel = "Close drawer",
  description,
  onClose,
  open,
  side = "right",
  title
}: DrawerProps) {
  const titleId = useId();
  const descriptionId = useId();
  const layerRef = useLayerInteraction({
    lockScroll: false,
    onClose,
    open,
    trapFocus: true
  });

  if (!open) {
    return null;
  }

  return (
    <OverlayPortal>
      <div className="ukde-overlay-scrim ukde-overlay-scrim-drawer">
        <div
          aria-describedby={description ? descriptionId : undefined}
          aria-labelledby={titleId}
          aria-modal="true"
          className={cx("ukde-drawer", className)}
          data-side={side}
          ref={layerRef}
          role="dialog"
          tabIndex={-1}
        >
          <header className="ukde-drawer-head">
            <div>
              <h2 id={titleId}>{title}</h2>
              {description ? (
                <p className="ukde-muted" id={descriptionId}>
                  {description}
                </p>
              ) : null}
            </div>
            <button
              aria-label={closeLabel}
              className="ukde-overlay-close"
              onClick={onClose}
              type="button"
            >
              Close
            </button>
          </header>
          <div className="ukde-drawer-body">{children}</div>
        </div>
      </div>
    </OverlayPortal>
  );
}

export type DetailsDrawerProps = Omit<DrawerProps, "side">;

export function DetailsDrawer(props: DetailsDrawerProps) {
  return <Drawer {...props} side="right" />;
}

export interface MenuFlyoutItem {
  disabled?: boolean;
  href?: string;
  id: string;
  label: string;
  onSelect?: () => void;
  tone?: PrimitiveTone;
}

export interface MenuFlyoutProps extends ClassNameProps {
  align?: "start" | "end";
  items: MenuFlyoutItem[];
  label: string;
}

function resolveNextMenuIndex(
  key: "ArrowDown" | "ArrowUp" | "Home" | "End",
  disabledStates: boolean[],
  activeIndex: number
): number {
  if (key === "Home") {
    return findFirstEnabledIndex(disabledStates);
  }
  if (key === "End") {
    for (let index = disabledStates.length - 1; index >= 0; index -= 1) {
      if (!disabledStates[index]) {
        return index;
      }
    }
    return -1;
  }
  return resolveToolbarTargetIndex(
    key === "ArrowDown" ? "ArrowRight" : "ArrowLeft",
    disabledStates,
    activeIndex
  );
}

export function MenuFlyout({
  align = "end",
  className,
  items,
  label
}: MenuFlyoutProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useLayerInteraction({
    closeOnOutsideClick: true,
    lockScroll: false,
    onClose: () => setOpen(false),
    open,
    returnFocusRef: triggerRef as MutableRefObject<HTMLElement | null>,
    trapFocus: false
  });
  const itemRefs = useRef<Array<HTMLElement | null>>([]);

  const disabledStates = useMemo(
    () => items.map((item) => Boolean(item.disabled)),
    [items]
  );

  useEffect(() => {
    if (!open) {
      return;
    }
    const firstEnabled = findFirstEnabledIndex(disabledStates);
    if (firstEnabled >= 0) {
      setActiveIndex(firstEnabled);
      itemRefs.current[firstEnabled]?.focus({ preventScroll: true });
    }
  }, [disabledStates, open]);

  const handleMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (
      event.key !== "ArrowDown" &&
      event.key !== "ArrowUp" &&
      event.key !== "Home" &&
      event.key !== "End"
    ) {
      return;
    }
    event.preventDefault();
    const targetIndex = resolveNextMenuIndex(
      event.key,
      disabledStates,
      activeIndex
    );
    if (targetIndex >= 0) {
      setActiveIndex(targetIndex);
      itemRefs.current[targetIndex]?.focus({ preventScroll: true });
    }
  };

  return (
    <div
      className={cx("ukde-menu-flyout", className)}
      data-open={open ? "yes" : "no"}
    >
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        className="ukde-button"
        onClick={() => setOpen((current) => !current)}
        ref={triggerRef}
        type="button"
      >
        {label}
      </button>
      {open ? (
        <div
          className="ukde-menu-surface"
          data-align={align}
          onKeyDown={handleMenuKeyDown}
          ref={menuRef}
          role="menu"
          tabIndex={-1}
        >
          {items.map((item, index) =>
            item.href ? (
              <a
                aria-disabled={item.disabled ? "true" : undefined}
                className="ukde-menu-item"
                data-tone={item.tone ?? "neutral"}
                href={item.href}
                key={item.id}
                onClick={(event) => {
                  if (item.disabled) {
                    event.preventDefault();
                    return;
                  }
                  item.onSelect?.();
                  setOpen(false);
                }}
                ref={(element) => {
                  itemRefs.current[index] = element;
                }}
                role="menuitem"
                tabIndex={index === activeIndex ? 0 : -1}
              >
                {item.label}
              </a>
            ) : (
              <button
                className="ukde-menu-item"
                data-tone={item.tone ?? "neutral"}
                disabled={item.disabled}
                key={item.id}
                onClick={() => {
                  item.onSelect?.();
                  setOpen(false);
                }}
                ref={(element) => {
                  itemRefs.current[index] = element;
                }}
                role="menuitem"
                tabIndex={index === activeIndex ? 0 : -1}
                type="button"
              >
                {item.label}
              </button>
            )
          )}
        </div>
      ) : null}
    </div>
  );
}

export interface CommandBarOverflowProps extends ClassNameProps {
  items: MenuFlyoutItem[];
  label?: string;
}

export function CommandBarOverflow({
  className,
  items,
  label = "More actions"
}: CommandBarOverflowProps) {
  return <MenuFlyout className={className} items={items} label={label} />;
}

export interface ToolbarAction {
  disabled?: boolean;
  id: string;
  label: string;
  onAction: () => void;
  pressed?: boolean;
  selected?: boolean;
  tone?: PrimitiveTone;
}

export interface ToolbarProps extends ClassNameProps {
  actions: ToolbarAction[];
  label: string;
  overflowActions?: MenuFlyoutItem[];
}

export function Toolbar({
  actions,
  className,
  label,
  overflowActions = []
}: ToolbarProps) {
  const disabledStates = useMemo(
    () => actions.map((action) => Boolean(action.disabled)),
    [actions]
  );
  const [activeIndex, setActiveIndex] = useState(() => {
    const firstEnabled = findFirstEnabledIndex(disabledStates);
    return firstEnabled >= 0 ? firstEnabled : 0;
  });
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    if (actions.length === 0) {
      return;
    }
    if (actions[activeIndex] && !actions[activeIndex].disabled) {
      return;
    }
    const fallback = findFirstEnabledIndex(disabledStates);
    if (fallback >= 0) {
      setActiveIndex(fallback);
    }
  }, [actions, activeIndex, disabledStates]);

  const moveFocus = useCallback((targetIndex: number) => {
    if (targetIndex < 0) {
      return;
    }
    setActiveIndex(targetIndex);
    refs.current[targetIndex]?.focus({ preventScroll: true });
  }, []);

  return (
    <div className={cx("ukde-toolbar-primitive", className)}>
      <div aria-label={label} className="ukde-toolbar-track" role="toolbar">
        {actions.map((action, index) => (
          <button
            aria-pressed={action.pressed}
            className="ukde-button"
            data-state={action.selected ? "selected" : undefined}
            data-tone={action.tone ?? "neutral"}
            disabled={action.disabled}
            key={action.id}
            onClick={action.onAction}
            onFocus={() => setActiveIndex(index)}
            onKeyDown={(event) => {
              if (
                event.key !== "ArrowLeft" &&
                event.key !== "ArrowRight" &&
                event.key !== "Home" &&
                event.key !== "End"
              ) {
                return;
              }
              event.preventDefault();
              const targetIndex = resolveToolbarTargetIndex(
                event.key,
                disabledStates,
                activeIndex
              );
              moveFocus(targetIndex);
            }}
            ref={(element) => {
              refs.current[index] = element;
            }}
            tabIndex={index === activeIndex ? 0 : -1}
            type="button"
          >
            {action.label}
          </button>
        ))}
      </div>
      {overflowActions.length > 0 ? (
        <CommandBarOverflow items={overflowActions} />
      ) : null}
    </div>
  );
}

export interface DataTableColumn<T> {
  header: string;
  key: string;
  renderCell: (row: T) => ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
}

export interface DataTableProps<T> extends ClassNameProps {
  caption: string;
  columns: DataTableColumn<T>[];
  emptyMessage?: string;
  errorMessage?: string | null;
  getRowId: (row: T) => string;
  loading?: boolean;
  onRowSelect?: (row: T | null) => void;
  pageSize?: number;
  renderRowActions?: (row: T) => ReactNode;
  rows: T[];
}

export function DataTable<T>({
  caption,
  className,
  columns,
  emptyMessage = "No rows to display.",
  errorMessage = null,
  getRowId,
  loading = false,
  onRowSelect,
  pageSize = 15,
  renderRowActions,
  rows
}: DataTableProps<T>) {
  const firstSortable = columns.find((column) => column.sortable);
  const [sortState, setSortState] = useState<{
    direction: SortDirection;
    key: string;
  } | null>(
    firstSortable
      ? {
          direction: "asc",
          key: firstSortable.key
        }
      : null
  );
  const [pageIndex, setPageIndex] = useState(0);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);

  const sortedRows = useMemo(() => {
    if (!sortState) {
      return rows;
    }
    const column = columns.find((candidate) => candidate.key === sortState.key);
    if (!column?.sortValue) {
      return rows;
    }
    return stableSortRows(rows, column.sortValue, sortState.direction);
  }, [columns, rows, sortState]);

  const maxPageIndex = Math.max(Math.ceil(sortedRows.length / pageSize) - 1, 0);
  const safePageIndex = Math.min(pageIndex, maxPageIndex);

  useEffect(() => {
    if (safePageIndex !== pageIndex) {
      setPageIndex(safePageIndex);
    }
  }, [pageIndex, safePageIndex]);

  const pagedRows = useMemo(() => {
    const start = safePageIndex * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [pageSize, safePageIndex, sortedRows]);

  useEffect(() => {
    if (!selectedRowId) {
      return;
    }
    const stillPresent = rows.some((row) => getRowId(row) === selectedRowId);
    if (!stillPresent) {
      setSelectedRowId(null);
      onRowSelect?.(null);
    }
  }, [getRowId, onRowSelect, rows, selectedRowId]);

  const totalPages = Math.max(Math.ceil(sortedRows.length / pageSize), 1);

  return (
    <div className={cx("ukde-data-table-wrap", className)}>
      <table className="ukde-data-table">
        <caption className="ukde-visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.sortable && column.sortValue ? (
                  <button
                    className="ukde-table-sort"
                    onClick={() => {
                      setSortState((current) => {
                        if (!current || current.key !== column.key) {
                          return { direction: "asc", key: column.key };
                        }
                        return {
                          direction:
                            current.direction === "asc" ? "desc" : "asc",
                          key: column.key
                        };
                      });
                    }}
                    type="button"
                  >
                    <span>{column.header}</span>
                    {sortState?.key === column.key ? (
                      <span aria-hidden>
                        {sortState.direction === "asc" ? "↑" : "↓"}
                      </span>
                    ) : null}
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
            {renderRowActions ? <th scope="col">Actions</th> : null}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length + (renderRowActions ? 1 : 0)}>
                <p className="ukde-muted">Loading rows…</p>
              </td>
            </tr>
          ) : errorMessage ? (
            <tr>
              <td colSpan={columns.length + (renderRowActions ? 1 : 0)}>
                <p className="ukde-muted">{errorMessage}</p>
              </td>
            </tr>
          ) : pagedRows.length === 0 ? (
            <tr>
              <td colSpan={columns.length + (renderRowActions ? 1 : 0)}>
                <p className="ukde-muted">{emptyMessage}</p>
              </td>
            </tr>
          ) : (
            pagedRows.map((row) => {
              const rowId = getRowId(row);
              return (
                <tr
                  aria-selected={selectedRowId === rowId}
                  className={
                    selectedRowId === rowId ? "is-selected" : undefined
                  }
                  key={rowId}
                  onClick={() => {
                    setSelectedRowId(rowId);
                    onRowSelect?.(row);
                  }}
                  onKeyDown={(event) => {
                    if (event.key !== "Enter" && event.key !== " ") {
                      return;
                    }
                    event.preventDefault();
                    setSelectedRowId(rowId);
                    onRowSelect?.(row);
                  }}
                  tabIndex={0}
                >
                  {columns.map((column) => (
                    <td key={column.key}>{column.renderCell(row)}</td>
                  ))}
                  {renderRowActions ? <td>{renderRowActions(row)}</td> : null}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
      <div className="ukde-data-table-footer">
        <span className="ukde-muted">
          Page {safePageIndex + 1} of {totalPages}
        </span>
        <div className="ukde-table-pagination">
          <button
            className="ukde-button"
            disabled={safePageIndex <= 0}
            onClick={() => setPageIndex((current) => Math.max(current - 1, 0))}
            type="button"
          >
            Previous
          </button>
          <button
            className="ukde-button"
            disabled={safePageIndex >= totalPages - 1}
            onClick={() =>
              setPageIndex((current) => Math.min(current + 1, totalPages - 1))
            }
            type="button"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

interface ToastRecord {
  description?: string;
  id: string;
  title: string;
  tone: PrimitiveTone;
}

export interface ToastInput {
  description?: string;
  durationMs?: number;
  title: string;
  tone?: PrimitiveTone;
}

interface ToastContextValue {
  dismissToast: (id: string) => void;
  pushToast: (toast: ToastInput) => string;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext);
  if (!value) {
    throw new Error("useToast must be called inside <ToastProvider>.");
  }
  return value;
}

export interface ToastProviderProps {
  children: ReactNode;
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const timers = useRef<Record<string, number>>({});

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timerId = timers.current[id];
    if (timerId) {
      window.clearTimeout(timerId);
      delete timers.current[id];
    }
  }, []);

  const pushToast = useCallback(
    ({ description, durationMs = 4200, title, tone = "info" }: ToastInput) => {
      const id = `toast-${Date.now()}-${Math.round(Math.random() * 10000)}`;
      setToasts((current) => [...current, { description, id, title, tone }]);
      timers.current[id] = window.setTimeout(
        () => dismissToast(id),
        durationMs
      );
      return id;
    },
    [dismissToast]
  );

  useEffect(
    () => () => {
      for (const timerId of Object.values(timers.current)) {
        window.clearTimeout(timerId);
      }
      timers.current = {};
    },
    []
  );

  return (
    <ToastContext.Provider value={{ dismissToast, pushToast }}>
      {children}
      <aside
        aria-atomic="false"
        aria-live="polite"
        className="ukde-toast-viewport"
      >
        {toasts.map((toast) => (
          <article
            className="ukde-toast"
            data-tone={toast.tone}
            key={toast.id}
            role="status"
          >
            <div className="ukde-toast-content">
              <strong>{toast.title}</strong>
              {toast.description ? <p>{toast.description}</p> : null}
            </div>
            <button
              aria-label="Dismiss notification"
              className="ukde-overlay-close"
              onClick={() => dismissToast(toast.id)}
              type="button"
            >
              Close
            </button>
          </article>
        ))}
      </aside>
    </ToastContext.Provider>
  );
}
