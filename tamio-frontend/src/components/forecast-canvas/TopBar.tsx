export function TopBar() {
  return (
    <header className="flex items-center px-4 py-3 glass-subtle rounded-xl mx-4 mt-2 mb-2">
      {/* Title + Live Badge */}
      <div className="flex items-center gap-3">
        <h1 className="text-base font-semibold text-gunmetal">
          Q1 2026 Forecast
        </h1>
        <div className="flex items-center gap-1.5 bg-lime/15 border border-lime/30 px-2.5 py-1 rounded-full">
          <span className="w-1.5 h-1.5 bg-lime-dark rounded-full status-pulse" />
          <span className="text-[11px] font-semibold text-lime-dark">
            Live
          </span>
        </div>
      </div>
    </header>
  );
}
