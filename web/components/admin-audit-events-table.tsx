"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { AuditEvent } from "@ukde/contracts";
import { DataTable, DetailsDrawer, StatusChip } from "@ukde/ui/primitives";

interface AdminAuditEventsTableProps {
  events: AuditEvent[];
}

export function AdminAuditEventsTable({ events }: AdminAuditEventsTableProps) {
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === selectedEventId) ?? null,
    [events, selectedEventId]
  );

  return (
    <>
      <DataTable
        caption="Audit events"
        columns={[
          {
            header: "Timestamp",
            key: "timestamp",
            renderCell: (row) => new Date(row.timestamp).toISOString(),
            sortable: true,
            sortValue: (row) => new Date(row.timestamp).getTime()
          },
          {
            header: "Event",
            key: "eventType",
            renderCell: (row) => row.eventType,
            sortable: true,
            sortValue: (row) => row.eventType
          },
          {
            header: "Actor",
            key: "actor",
            renderCell: (row) => row.actorUserId ?? "-",
            sortable: true,
            sortValue: (row) => row.actorUserId ?? ""
          },
          {
            header: "Project",
            key: "project",
            renderCell: (row) => row.projectId ?? "-",
            sortable: true,
            sortValue: (row) => row.projectId ?? ""
          },
          {
            header: "Request ID",
            key: "requestId",
            renderCell: (row) => row.requestId,
            sortable: true,
            sortValue: (row) => row.requestId
          }
        ]}
        emptyMessage="No events matched the current filters."
        getRowId={(row) => row.id}
        onRowSelect={(row) => setSelectedEventId(row?.id ?? null)}
        pageSize={20}
        renderRowActions={(row) => (
          <Link className="ukde-link" href={`/admin/audit/${row.id}`}>
            Open
          </Link>
        )}
        rows={events}
      />

      <DetailsDrawer
        description="Append-only event details without leaving the current review surface."
        onClose={() => setSelectedEventId(null)}
        open={Boolean(selectedEvent)}
        title="Audit event summary"
      >
        {selectedEvent ? (
          <>
            <div className="auditIntegrityRow">
              <StatusChip tone="info">{selectedEvent.eventType}</StatusChip>
              <StatusChip tone="neutral">
                Chain #{selectedEvent.chainIndex}
              </StatusChip>
            </div>
            <ul className="projectMetaList">
              <li>
                <span>Event ID</span>
                <strong>{selectedEvent.id}</strong>
              </li>
              <li>
                <span>Timestamp</span>
                <strong>
                  {new Date(selectedEvent.timestamp).toISOString()}
                </strong>
              </li>
              <li>
                <span>Actor</span>
                <strong>{selectedEvent.actorUserId ?? "-"}</strong>
              </li>
              <li>
                <span>Project</span>
                <strong>{selectedEvent.projectId ?? "-"}</strong>
              </li>
              <li>
                <span>Request ID</span>
                <strong>{selectedEvent.requestId}</strong>
              </li>
            </ul>
            <p className="ukde-eyebrow">Metadata</p>
            <pre className="statusDetail">
              {JSON.stringify(selectedEvent.metadataJson, null, 2)}
            </pre>
            <Link
              className="ukde-link"
              href={`/admin/audit/${selectedEvent.id}`}
            >
              Open full audit event
            </Link>
          </>
        ) : null}
      </DetailsDrawer>
    </>
  );
}
