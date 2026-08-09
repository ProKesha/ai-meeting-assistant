import { MeetingDashboard } from "@/components/meeting-dashboard";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#f5f7f8]">
      <header className="border-b border-[#dfe5e8] bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#123a4a] text-sm font-bold tracking-tight text-white shadow-sm">
              AM
            </div>
            <div>
              <p className="text-sm font-semibold tracking-tight text-[#102f3b] sm:text-base">
                AI Meeting Assistant
              </p>
              <p className="hidden text-xs text-[#718087] sm:block">Your meeting workspace</p>
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-[#dce5e4] bg-[#f6faf9] px-3 py-1.5 text-xs font-medium text-[#35665d]">
            <span className="h-2 w-2 rounded-full bg-[#3b9b78]" aria-hidden="true" />
            Ready for your next meeting
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
        <section className="mb-9 max-w-3xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-[#397568]">
            Meeting knowledge, made useful
          </p>
          <h1 className="text-balance text-3xl font-semibold tracking-[-0.035em] text-[#102f3b] sm:text-5xl sm:leading-[1.08]">
            Make every meeting useful after it ends.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[#607078] sm:text-lg">
            Turn meeting recordings into summaries, action items, and searchable knowledge.
          </p>
        </section>

        <MeetingDashboard />

        <footer className="mt-12 flex flex-col gap-2 border-t border-[#dfe5e8] pt-6 text-xs text-[#7b898f] sm:flex-row sm:items-center sm:justify-between">
          <p>Upload, review, and ask—all from one focused workspace.</p>
          <p>MP3, WAV, and M4A · Up to 50 MB</p>
        </footer>
      </div>
    </main>
  );
}
