"use client";

import { useMemo, useState } from "react";

import type { MenuFlyoutItem } from "@ukde/ui/primitives";
import {
  BannerAlert,
  Breadcrumbs,
  CommandBarOverflow,
  DataTable,
  DetailsDrawer,
  Drawer,
  InlineAlert,
  MenuFlyout,
  ModalDialog,
  StatusChip,
  ToastProvider,
  Toolbar,
  useToast
} from "@ukde/ui/primitives";

interface PrimitiveRow {
  id: string;
  owner: string;
  status: "Ready" | "Queued" | "Failed";
  title: string;
}

const SAMPLE_ROWS: PrimitiveRow[] = [
  {
    id: "doc-001",
    owner: "researcher.a",
    status: "Ready",
    title: "Diary_1871"
  },
  {
    id: "doc-002",
    owner: "reviewer.b",
    status: "Queued",
    title: "Parish_Logs"
  },
  { id: "doc-003", owner: "lead.c", status: "Failed", title: "Estate_Notes" }
];

function PrimitiveShowcaseBody() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const { pushToast } = useToast();

  const selectedRow = useMemo(
    () => SAMPLE_ROWS.find((row) => row.id === selectedRowId) ?? null,
    [selectedRowId]
  );

  const overflowItems: MenuFlyoutItem[] = [
    {
      id: "overflow-export",
      label: "Queue export check",
      onSelect: () =>
        pushToast({
          title: "Export check queued",
          description: "Low-risk command routed through toolbar overflow.",
          tone: "info"
        })
    },
    {
      id: "overflow-pin",
      label: "Pin current workspace",
      onSelect: () =>
        pushToast({
          title: "Workspace pinned",
          description: "Context restored for the next visit.",
          tone: "success"
        })
    }
  ];

  return (
    <section className="sectionCard ukde-panel dsSection">
      <div className="sectionHeading">
        <p className="ukde-eyebrow">Primitive showcase</p>
        <h2>
          Dialogs, drawers, menus, toasts, breadcrumbs, toolbar, and table
        </h2>
      </div>

      <Breadcrumbs
        items={[
          { href: "/admin", label: "Admin" },
          { href: "/admin/design-system", label: "Design system" },
          { label: "Primitive showcase" }
        ]}
      />

      <div className="dsSectionControls">
        <button
          className="ukde-button"
          data-variant="primary"
          onClick={() => setDialogOpen(true)}
          type="button"
        >
          Open dialog
        </button>
        <button
          className="ukde-button"
          onClick={() => setDrawerOpen(true)}
          type="button"
        >
          Open drawer
        </button>
        <MenuFlyout
          items={[
            {
              id: "menu-1",
              label: "Create follow-up",
              onSelect: () =>
                pushToast({
                  title: "Follow-up created",
                  description: "Menu actions remain keyboard reachable.",
                  tone: "success"
                })
            },
            {
              id: "menu-2",
              label: "Flag for review",
              onSelect: () =>
                pushToast({
                  title: "Flagged for review",
                  description: "Secondary action moved into flyout.",
                  tone: "warning"
                })
            }
          ]}
          label="Open menu"
        />
        <CommandBarOverflow items={overflowItems} />
      </div>

      <Toolbar
        actions={[
          {
            id: "toolbar-refresh",
            label: "Refresh",
            onAction: () =>
              pushToast({
                title: "Surface refreshed",
                description: "Toolbar actions use roving keyboard focus.",
                tone: "info"
              })
          },
          {
            id: "toolbar-filter",
            label: "Filter open only",
            onAction: () =>
              pushToast({
                title: "Filter set",
                description: "Current rows constrained to active items.",
                tone: "success"
              }),
            selected: true
          },
          {
            disabled: true,
            id: "toolbar-delete",
            label: "Delete",
            onAction: () => undefined
          }
        ]}
        label="Primitive toolbar"
        overflowActions={[
          {
            id: "toolbar-overflow-resync",
            label: "Resync index",
            onSelect: () =>
              pushToast({
                title: "Index resync queued",
                description: "Low-frequency command moved to overflow.",
                tone: "info"
              })
          }
        ]}
      />

      <div className="dsSectionControls">
        <StatusChip tone="success">READY</StatusChip>
        <StatusChip tone="warning">QUEUED</StatusChip>
        <StatusChip tone="danger">FAILED</StatusChip>
        <StatusChip tone="info">CONTROLLED</StatusChip>
      </div>

      <InlineAlert title="Inline route guidance" tone="info">
        Use dialogs for blocking confirmation and drawers for contextual detail.
      </InlineAlert>
      <BannerAlert
        actions={
          <button
            className="ukde-button"
            onClick={() =>
              pushToast({
                title: "Banner action acknowledged",
                tone: "success"
              })
            }
            type="button"
          >
            Acknowledge
          </button>
        }
        title="Banner-level status"
        tone="warning"
      >
        Important workflow guidance should stay visible in-line, not only in
        toasts.
      </BannerAlert>

      <DataTable
        caption="Primitive data table"
        columns={[
          {
            header: "Document",
            key: "title",
            renderCell: (row) => row.title,
            sortable: true,
            sortValue: (row) => row.title
          },
          {
            header: "Status",
            key: "status",
            renderCell: (row) => (
              <StatusChip
                tone={
                  row.status === "Ready"
                    ? "success"
                    : row.status === "Queued"
                      ? "warning"
                      : "danger"
                }
              >
                {row.status}
              </StatusChip>
            ),
            sortable: true,
            sortValue: (row) => row.status
          },
          {
            header: "Owner",
            key: "owner",
            renderCell: (row) => row.owner,
            sortable: true,
            sortValue: (row) => row.owner
          }
        ]}
        getRowId={(row) => row.id}
        onRowSelect={(row) => setSelectedRowId(row?.id ?? null)}
        pageSize={5}
        rows={SAMPLE_ROWS}
      />

      <ModalDialog
        description="This modal demonstrates focus trap, escape handling, and focus return."
        footer={
          <>
            <button
              className="ukde-button"
              onClick={() => setDialogOpen(false)}
              type="button"
            >
              Cancel
            </button>
            <button
              className="ukde-button"
              data-variant="primary"
              onClick={() => {
                setDialogOpen(false);
                pushToast({
                  title: "Dialog confirmed",
                  tone: "success"
                });
              }}
              type="button"
            >
              Confirm
            </button>
          </>
        }
        onClose={() => setDialogOpen(false)}
        open={dialogOpen}
        title="Confirm project-level action"
      >
        <p className="ukde-muted">
          The active element returns to the invoking button after this dialog
          closes.
        </p>
      </ModalDialog>

      <Drawer
        description="Contextual side panel with bounded internal scrolling."
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        title="Context drawer"
      >
        <p className="ukde-muted">
          Use drawers for secondary metadata or audit context without expanding
          page height.
        </p>
        <ul className="projectMetaList">
          <li>
            <span>Keyboard close</span>
            <strong>Escape</strong>
          </li>
          <li>
            <span>Focus return</span>
            <strong>Enabled</strong>
          </li>
          <li>
            <span>Outside click close</span>
            <strong>Enabled</strong>
          </li>
        </ul>
      </Drawer>

      <DetailsDrawer
        description="Details drawer composition over shared drawer primitive."
        onClose={() => setSelectedRowId(null)}
        open={Boolean(selectedRow)}
        title={selectedRow ? `Details: ${selectedRow.title}` : "Details"}
      >
        {selectedRow ? (
          <ul className="projectMetaList">
            <li>
              <span>Document ID</span>
              <strong>{selectedRow.id}</strong>
            </li>
            <li>
              <span>Owner</span>
              <strong>{selectedRow.owner}</strong>
            </li>
            <li>
              <span>Status</span>
              <strong>{selectedRow.status}</strong>
            </li>
          </ul>
        ) : null}
      </DetailsDrawer>
    </section>
  );
}

export function DesignSystemPrimitivesShowcase() {
  return (
    <ToastProvider>
      <PrimitiveShowcaseBody />
    </ToastProvider>
  );
}
