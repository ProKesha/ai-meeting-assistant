import type { MeetingListItemResponse } from "@/lib/api";

const statusStyles: Record<string, string> = {
  completed: "border-[#c9dfd8] bg-[#edf7f4] text-[#397568]",
  failed: "border-[#ebcaca] bg-[#fff4f4] text-[#a04b4b]",
  processing: "border-[#d7dced] bg-[#f3f5fb] text-[#586b9a]",
  uploaded: "border-[#d8e2e6] bg-[#f4f7f8] text-[#5f737c]",
  created: "border-[#d8e2e6] bg-[#f4f7f8] text-[#5f737c]",
};

function formatCreatedAt(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function RecentMeetings({
  meetings,
  isLoading,
  error,
  selectedId,
  onSelect,
}: {
  meetings: MeetingListItemResponse[];
  isLoading: boolean;
  error: string | null;
  selectedId: string | null;
  onSelect: (meeting: MeetingListItemResponse) => void;
}) {
  return (
    <section className="mt-8 rounded-3xl border border-[#dce3e6] bg-white p-5 shadow-[0_12px_40px_rgba(16,47,59,0.05)] sm:p-7">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#718087]">History</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-[#173540]">Recent meetings</h2>
        </div>
        <p className="text-xs text-[#8a979c]">Latest 10</p>
      </div>

      {isLoading ? (
        <p className="rounded-xl bg-[#f7f9f9] px-4 py-5 text-sm text-[#718087]" role="status">
          Loading recent meetings…
        </p>
      ) : error ? (
        <p className="rounded-xl border border-[#ebcaca] bg-[#fff4f4] px-4 py-3 text-sm text-[#914545]" role="alert">
          {error}
        </p>
      ) : meetings.length === 0 ? (
        <p className="rounded-xl bg-[#f7f9f9] px-4 py-5 text-sm text-[#718087]">
          Process your first meeting and it will appear here.
        </p>
      ) : (
        <div className="divide-y divide-[#e7ebed]">
          {meetings.map((meeting) => {
            const isCompleted = meeting.status === "completed";
            const isSelected = selectedId === meeting.id;
            return (
              <button
                key={meeting.id}
                type="button"
                onClick={() => onSelect(meeting)}
                disabled={!isCompleted}
                className={`w-full px-1 py-4 text-left transition first:pt-1 last:pb-1 ${
                  isCompleted ? "cursor-pointer hover:bg-[#fafcfc]" : "cursor-default"
                } ${isSelected ? "bg-[#f6faf9]" : ""}`}
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#294650]">{meeting.title}</p>
                    <p className="mt-1 text-xs text-[#829097]">{formatCreatedAt(meeting.created_at)}</p>
                  </div>
                  <span
                    className={`w-fit rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${
                      statusStyles[meeting.status] ?? statusStyles.created
                    }`}
                  >
                    {meeting.status}
                  </span>
                </div>
                {meeting.summary && (
                  <p className="mt-2 line-clamp-2 text-sm leading-6 text-[#66777c]">{meeting.summary}</p>
                )}
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
