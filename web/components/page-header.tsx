"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useMemo } from "react";
import { useRouter } from "next/navigation";

import { CommandBarOverflow, type MenuFlyoutItem } from "@ukde/ui/primitives";

interface PageHeaderAction {
  href: string;
  label: string;
}

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  summary?: string;
  primaryAction?: PageHeaderAction;
  secondaryActions?: PageHeaderAction[];
  overflowActions?: PageHeaderAction[];
  overflowLabel?: string;
  meta?: ReactNode;
}

export function PageHeader({
  eyebrow,
  title,
  summary,
  primaryAction,
  secondaryActions = [],
  overflowActions = [],
  overflowLabel = "More actions",
  meta
}: PageHeaderProps) {
  const router = useRouter();
  const overflowMenuItems = useMemo<MenuFlyoutItem[]>(
    () =>
      overflowActions.map((action) => ({
        id: action.href,
        label: action.label,
        onSelect: () => {
          router.push(action.href);
        }
      })),
    [overflowActions, router]
  );

  return (
    <section className="pageHeader ukde-panel" aria-live="polite">
      <div className="pageHeaderIdentity">
        {eyebrow ? <p className="ukde-eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {summary ? <p className="ukde-muted">{summary}</p> : null}
        {meta ? <div className="pageHeaderMeta">{meta}</div> : null}
      </div>

      {primaryAction ||
      secondaryActions.length > 0 ||
      overflowActions.length > 0 ? (
        <div className="pageHeaderActions">
          {secondaryActions.map((action) => (
            <Link
              className="secondaryButton"
              href={action.href}
              key={action.href}
            >
              {action.label}
            </Link>
          ))}
          {overflowMenuItems.length > 0 ? (
            <CommandBarOverflow
              items={overflowMenuItems}
              label={overflowLabel}
            />
          ) : null}
          {primaryAction ? (
            <Link className="primaryButton" href={primaryAction.href}>
              {primaryAction.label}
            </Link>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
