import type { MeetingResultData } from "@/lib/api";
import { ActionItemCard } from "./action-item-card";

function EmptyState({ children }: { children: string }) {
  return <p className="text-sm leading-6 text-[#7b898f]">{children}</p>;
}

export function MeetingResults({ result }: { result: MeetingResultData }) {
  const { analysis } = result;

  return (
    <section id="meeting-results" className="mt-8 space-y-5" aria-labelledby="results-heading">
      <div className="flex flex-col gap-3 rounded-2xl border border-[#cfe0dc] bg-[#edf7f4] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#397568]">Complete</p>
          <h2 id="results-heading" className="mt-1 text-xl font-semibold tracking-tight text-[#173540]">
            Your meeting is ready
          </h2>
        </div>
        <div className="flex items-center gap-2 text-xs text-[#5d766f]">
          <span className="rounded-full border border-[#c9dcd7] bg-white px-2.5 py-1">Transcribed</span>
          <span className="rounded-full border border-[#c9dcd7] bg-white px-2.5 py-1">Analyzed</span>
        </div>
      </div>

      <article className="rounded-2xl border border-[#dfe5e8] bg-white p-5 shadow-[0_8px_28px_rgba(16,47,59,0.05)] sm:p-6">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#718087]">Summary</p>
        <p className="mt-3 text-base leading-7 text-[#294650]">{analysis.summary}</p>
      </article>

      <div className="grid gap-5 lg:grid-cols-2">
        <article className="rounded-2xl border border-[#dfe5e8] bg-white p-5 shadow-[0_8px_28px_rgba(16,47,59,0.04)] sm:p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-[#173540]">Decisions</h3>
            <span className="rounded-full bg-[#eef3f4] px-2.5 py-1 text-xs font-semibold text-[#62757c]">
              {analysis.decisions.length}
            </span>
          </div>
          {analysis.decisions.length ? (
            <ul className="space-y-3">
              {analysis.decisions.map((decision, index) => (
                <li key={`${decision}-${index}`} className="flex gap-3 text-sm leading-6 text-[#52676f]">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#397568]" aria-hidden="true" />
                  {decision}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>No explicit decisions were recorded.</EmptyState>
          )}
        </article>

        <article className="rounded-2xl border border-[#dfe5e8] bg-white p-5 shadow-[0_8px_28px_rgba(16,47,59,0.04)] sm:p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-[#173540]">Open questions</h3>
            <span className="rounded-full bg-[#eef3f4] px-2.5 py-1 text-xs font-semibold text-[#62757c]">
              {analysis.open_questions.length}
            </span>
          </div>
          {analysis.open_questions.length ? (
            <ul className="space-y-3">
              {analysis.open_questions.map((question, index) => (
                <li key={`${question}-${index}`} className="flex gap-3 text-sm leading-6 text-[#52676f]">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#f0f3f4] text-[11px] font-bold text-[#62757c]">
                    ?
                  </span>
                  {question}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState>No unresolved questions were identified.</EmptyState>
          )}
        </article>
      </div>

      <article className="rounded-2xl border border-[#dfe5e8] bg-[#f9fafb] p-5 sm:p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold text-[#173540]">Action items</h3>
          <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-[#62757c] shadow-sm">
            {analysis.action_items.length}
          </span>
        </div>
        {analysis.action_items.length ? (
          <div className="space-y-3">
            {analysis.action_items.map((item, index) => (
              <ActionItemCard key={`${item.task}-${index}`} item={item} index={index} />
            ))}
          </div>
        ) : (
          <EmptyState>No explicit action items were identified.</EmptyState>
        )}
      </article>

      <details className="group rounded-2xl border border-[#dfe5e8] bg-white shadow-[0_4px_20px_rgba(16,47,59,0.03)]">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-medium text-[#294650] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#397568] sm:px-6">
          <span>
            View transcript
            <span className="ml-2 text-xs font-normal text-[#829097]">Full meeting text</span>
          </span>
          <span
            className="flex h-7 w-7 items-center justify-center rounded-full bg-[#f0f3f4] text-lg text-[#62757c] transition-transform group-open:rotate-45"
            aria-hidden="true"
          >
            +
          </span>
        </summary>
        <div className="border-t border-[#e5eaec] px-5 py-5 sm:px-6">
          <p className="whitespace-pre-wrap text-sm leading-7 text-[#5f7077]">{result.transcript}</p>
        </div>
      </details>
    </section>
  );
}
