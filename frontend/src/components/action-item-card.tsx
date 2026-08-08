import type { ActionItem, Priority } from "@/lib/api";

const priorityStyles: Record<Priority, string> = {
  low: "border-[#d8e2e6] bg-[#f4f7f8] text-[#5f737c]",
  medium: "border-[#e8d9b2] bg-[#fff8e8] text-[#8a6825]",
  high: "border-[#ebc8c8] bg-[#fff1f1] text-[#a04444]",
};

export function ActionItemCard({ item, index }: { item: ActionItem; index: number }) {
  return (
    <article className="rounded-xl border border-[#dfe5e8] bg-white p-4 shadow-[0_1px_2px_rgba(16,47,59,0.03)]">
      <div className="flex items-start gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#eef3f4] text-xs font-bold text-[#46616b]">
          {index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <h4 className="font-semibold leading-6 text-[#173540]">{item.task}</h4>
            <span
              className={`w-fit rounded-full border px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityStyles[item.priority]}`}
            >
              {item.priority} priority
            </span>
          </div>
          <dl className="mt-3 grid gap-2 text-sm text-[#697980] sm:grid-cols-2">
            <div className="flex gap-2">
              <dt className="font-medium text-[#405963]">Assignee:</dt>
              <dd>{item.assignee ?? "Not specified"}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium text-[#405963]">Deadline:</dt>
              <dd>{item.deadline ?? "Not specified"}</dd>
            </div>
          </dl>
        </div>
      </div>
    </article>
  );
}
