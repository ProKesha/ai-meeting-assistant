"use client";

import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import {
  askMeetings,
  type AskMeetingsResponse,
} from "@/lib/api";

const GROUNDED_FALLBACK =
  "I couldn't find enough information in the stored meetings to answer that.";

function isGroundedFallback(response: AskMeetingsResponse): boolean {
  return response.answer.trim() === GROUNDED_FALLBACK || response.sources.length === 0;
}

export function AskMeetings({
  onOpenMeeting,
}: {
  onOpenMeeting: (meetingId: string) => void;
}) {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<AskMeetingsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedQuestion = question.trim();
    if (!normalizedQuestion || isLoading) return;

    setIsLoading(true);
    setError(null);
    setResponse(null);

    try {
      setResponse(
        await askMeetings({
          question: normalizedQuestion,
          limit: 5,
          meeting_id: null,
        }),
      );
    } catch {
      setError(
        "I couldn’t answer this right now. Make sure the local AI service is running and try again.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  const hasFallback = response ? isGroundedFallback(response) : false;

  return (
    <section
      className="flex min-h-full flex-col overflow-hidden rounded-3xl border border-[#dce3e6] bg-white shadow-[0_18px_55px_rgba(16,47,59,0.07)]"
      aria-labelledby="ask-meetings-heading"
    >
      <div className="border-b border-[#e4e9eb] px-5 py-5 sm:px-6">
        <div className="flex items-start gap-3">
          <span
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#e7f2ef] text-[#2f6f61]"
            aria-hidden="true"
          >
            ?
          </span>
          <div>
            <h2
              id="ask-meetings-heading"
              className="text-lg font-semibold tracking-tight text-[#173540]"
            >
              Ask your meetings
            </h2>
            <p className="mt-1 text-sm leading-6 text-[#74838a]">
              Get an answer grounded in your previous meeting transcripts.
            </p>
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="border-b border-[#e4e9eb] p-5 sm:p-6">
        <label
          htmlFor="meeting-question"
          className="mb-2 block text-sm font-semibold text-[#294650]"
        >
          What would you like to know?
        </label>
        <textarea
          id="meeting-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleQuestionKeyDown}
          placeholder="What did we decide about the product launch?"
          rows={5}
          disabled={isLoading}
          aria-describedby="meeting-question-hint"
          className="w-full resize-none rounded-xl border border-[#ccd6da] bg-white px-3.5 py-3 text-sm leading-6 text-[#1d3c47] outline-none transition placeholder:text-[#9aa6ab] focus:border-[#397568] focus:ring-[3px] focus:ring-[#397568]/10 disabled:bg-[#f5f7f8]"
        />
        <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p id="meeting-question-hint" className="text-xs text-[#829097]">
            Press Ctrl or ⌘ + Enter to ask
          </p>
          <button
            type="submit"
            disabled={isLoading || !question.trim()}
            className="inline-flex h-11 items-center justify-center rounded-xl bg-[#397568] px-5 text-sm font-semibold text-white shadow-[0_5px_15px_rgba(57,117,104,0.2)] transition hover:bg-[#2d665a] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#397568] disabled:cursor-not-allowed disabled:opacity-55"
          >
            {isLoading ? (
              <>
                <span
                  className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white/35 border-t-white"
                  aria-hidden="true"
                />
                Finding an answer…
              </>
            ) : (
              <>
                Ask
                <span className="ml-2" aria-hidden="true">
                  →
                </span>
              </>
            )}
          </button>
        </div>
      </form>

      <div className="flex flex-1 flex-col p-5 sm:p-6" aria-live="polite">
        {isLoading ? (
          <div className="flex min-h-40 flex-1 items-center justify-center rounded-2xl bg-[#f6faf9] px-5 text-center">
            <div>
              <span
                className="mx-auto block h-8 w-8 animate-spin rounded-full border-[3px] border-[#c9ddd8] border-t-[#397568]"
                aria-hidden="true"
              />
              <p className="mt-3 text-sm font-medium text-[#405963]">
                Looking through your meetings…
              </p>
            </div>
          </div>
        ) : error ? (
          <div
            className="rounded-2xl border border-[#ebcaca] bg-[#fff5f5] px-4 py-4 text-sm leading-6 text-[#914545]"
            role="alert"
          >
            {error}
          </div>
        ) : response && hasFallback ? (
          <div className="rounded-2xl border border-[#dce4e6] bg-[#f7f9f9] px-4 py-5">
            <p className="font-semibold text-[#405963]">Not enough information yet</p>
            <p className="mt-2 text-sm leading-6 text-[#6f7f85]">
              I couldn’t find enough information in your meetings to answer this question.
            </p>
          </div>
        ) : response ? (
          <div className="space-y-5">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#718087]">
                Answer
              </p>
              <p className="mt-2 text-[15px] leading-7 text-[#294650]">{response.answer}</p>
            </div>

            <div>
              <div className="mb-2 flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-[#405963]">Sources</h3>
                <span className="text-xs text-[#8a979c]">
                  {response.sources.length} {response.sources.length === 1 ? "source" : "sources"}
                </span>
              </div>
              <div className="space-y-2">
                {response.sources.map((source, index) => (
                  <button
                    key={source.chunk_id}
                    type="button"
                    onClick={() => onOpenMeeting(source.meeting_id)}
                    className="group w-full rounded-xl border border-[#dfe5e8] bg-[#fafcfc] px-3.5 py-3 text-left transition hover:border-[#aac6bf] hover:bg-[#f5faf8] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#397568]"
                  >
                    <span className="block truncate text-sm font-semibold text-[#294650] group-hover:text-[#2f6f61]">
                      {source.meeting_title}
                    </span>
                    <span className="mt-1 block text-xs text-[#829097]">
                      Source {index + 1} · Transcript section {source.chunk_index + 1}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex min-h-40 flex-1 items-center justify-center rounded-2xl border border-dashed border-[#d8e1e3] bg-[#fafcfc] px-5 text-center">
            <div>
              <p className="text-sm font-semibold text-[#52676f]">Your answer will appear here</p>
              <p className="mt-1 max-w-xs text-xs leading-5 text-[#8a979c]">
                Answers use only information found in your processed meetings.
              </p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
