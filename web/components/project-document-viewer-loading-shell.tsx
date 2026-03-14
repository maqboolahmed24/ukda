import { SkeletonLines } from "@ukde/ui/primitives";

export function ProjectDocumentViewerLoadingShell() {
  return (
    <>
      <section className="documentViewerToolbar ukde-panel">
        <div className="documentViewerToolbarRow">
          <SkeletonLines lines={1} />
          <div className="documentViewerLoadingChip" />
          <div className="documentViewerLoadingChip" />
        </div>
      </section>

      <section className="documentViewerWorkspace ukde-panel" aria-busy="true">
        <aside className="documentViewerFilmstrip" aria-label="Filmstrip loading">
          <h2>Pages</h2>
          <ul className="documentViewerSkeletonRail">
            {Array.from({ length: 7 }).map((_, index) => (
              <li className="documentViewerSkeletonThumb" key={`thumb-${index}`} />
            ))}
          </ul>
        </aside>

        <section className="documentViewerCanvas" aria-label="Canvas loading">
          <div className="documentViewerCanvasViewport">
            <div className="documentViewerSkeletonCanvas">
              <SkeletonLines lines={2} />
            </div>
          </div>
        </section>

        <aside className="documentViewerInspector" aria-label="Inspector loading">
          <h2>Inspector</h2>
          <SkeletonLines lines={6} />
        </aside>
      </section>
    </>
  );
}
