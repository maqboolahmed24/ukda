"use client";

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="loadingScreen ukde-panel">
      <p className="ukde-eyebrow">Route failure</p>
      <h1>The shell hit an unexpected boundary.</h1>
      <p className="ukde-muted">{error.message}</p>
      <button className="primaryButton" onClick={() => reset()} type="button">
        Retry route
      </button>
    </main>
  );
}
