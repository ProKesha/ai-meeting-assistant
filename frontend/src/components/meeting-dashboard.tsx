"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getMeeting,
  getMeetings,
  type MeetingListItemResponse,
  type MeetingProcessResponse,
  type MeetingResultData,
} from "@/lib/api";
import { AskMeetings } from "./ask-meetings";
import { MeetingResults } from "./meeting-results";
import { MeetingUploadForm } from "./meeting-upload-form";
import { RecentMeetings } from "./recent-meetings";

export function MeetingDashboard() {
  const [meetings, setMeetings] = useState<MeetingListItemResponse[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingMeetingId, setLoadingMeetingId] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [result, setResult] = useState<MeetingResultData | null>(null);

  const refreshMeetings = useCallback(async () => {
    try {
      setMeetings(await getMeetings(10));
      setHistoryError(null);
    } catch {
      setHistoryError("Could not load recent meetings.");
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    getMeetings(10)
      .then((recentMeetings) => {
        if (!ignore) {
          setMeetings(recentMeetings);
          setHistoryError(null);
        }
      })
      .catch(() => {
        if (!ignore) setHistoryError("Could not load recent meetings.");
      })
      .finally(() => {
        if (!ignore) setIsHistoryLoading(false);
      });

    return () => {
      ignore = true;
    };
  }, []);

  async function openMeeting(meetingId: string) {
    setLoadingMeetingId(meetingId);
    setDetailError(null);

    try {
      const stored = await getMeeting(meetingId);
      if (!stored.analysis || !stored.transcript) {
        setDetailError("This meeting does not have a complete stored result yet.");
        return;
      }
      setSelectedId(stored.id);
      setResult({ analysis: stored.analysis, transcript: stored.transcript });
      setTimeout(() => {
        document.getElementById("meeting-results")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 50);
    } catch {
      setDetailError("Could not open this meeting. Please try again.");
    } finally {
      setLoadingMeetingId(null);
    }
  }

  function selectMeeting(meeting: MeetingListItemResponse) {
    if (meeting.status === "completed") void openMeeting(meeting.id);
  }

  function handleProcessed(processed: MeetingProcessResponse) {
    setSelectedId(processed.meeting_id);
    setResult(processed);
    setDetailError(null);
    setIsHistoryLoading(true);
    void refreshMeetings();
  }

  return (
    <>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <MeetingUploadForm onProcessed={handleProcessed} />
        <AskMeetings onOpenMeeting={(meetingId) => void openMeeting(meetingId)} />
      </div>

      {detailError && (
        <p
          className="mt-6 rounded-2xl border border-[#ebcaca] bg-[#fff4f4] px-4 py-3 text-sm text-[#914545]"
          role="alert"
        >
          {detailError}
        </p>
      )}

      {result && <MeetingResults result={result} />}

      <RecentMeetings
        meetings={meetings}
        isLoading={isHistoryLoading}
        error={historyError}
        selectedId={selectedId}
        loadingMeetingId={loadingMeetingId}
        onSelect={selectMeeting}
      />
    </>
  );
}
