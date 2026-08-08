export type ProcessingStage = "creating" | "uploading" | "transcribing" | "analyzing";

const stages: Array<{ key: ProcessingStage; label: string; detail: string }> = [
  { key: "creating", label: "Creating meeting", detail: "Preparing your workspace" },
  { key: "uploading", label: "Uploading audio", detail: "Sending your recording securely" },
  { key: "transcribing", label: "Transcribing meeting", detail: "Turning speech into text" },
  { key: "analyzing", label: "Analyzing meeting", detail: "Finding decisions and next steps" },
];

export function ProcessingState({ stage }: { stage: ProcessingStage }) {
  const activeIndex = stages.findIndex((item) => item.key === stage);

  return (
    <div
      className="rounded-2xl border border-[#cddfdb] bg-[#f6faf9] p-5"
      role="status"
      aria-live="polite"
    >
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-[#173f48]">Processing your meeting</p>
          <p className="mt-1 text-xs text-[#698078]">You can keep this page open while we work.</p>
        </div>
        <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-[#397568] shadow-sm">
          Step {activeIndex + 1} of {stages.length}
        </span>
      </div>

      <ol className="space-y-3">
        {stages.map((item, index) => {
          const isComplete = index < activeIndex;
          const isActive = index === activeIndex;
          return (
            <li key={item.key} className="flex items-center gap-3">
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  isComplete
                    ? "bg-[#397568] text-white"
                    : isActive
                      ? "border-2 border-[#397568] bg-white text-[#397568]"
                      : "border border-[#d6dfdd] bg-white text-[#9aa7a3]"
                }`}
                aria-hidden="true"
              >
                {isComplete ? "✓" : isActive ? (
                  <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-[#397568]" />
                ) : (
                  index + 1
                )}
              </span>
              <div>
                <p
                  className={`text-sm font-medium ${isActive ? "text-[#173f48]" : "text-[#66777c]"}`}
                >
                  {item.label}
                </p>
                {isActive && <p className="text-xs text-[#758680]">{item.detail}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
