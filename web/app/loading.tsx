export default function Loading() {
  return (
    <main
      className="loadingScreen ukde-panel"
      aria-busy="true"
      aria-live="polite"
    >
      <p className="ukde-eyebrow">Loading</p>
      <h1>Preparing the secure shell.</h1>
      <p className="ukde-muted">
        The bootstrap keeps transitions quiet and immediate.
      </p>
    </main>
  );
}
