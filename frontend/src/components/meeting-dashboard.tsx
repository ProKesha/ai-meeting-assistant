"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getMeeting,
  getMeetings,
  type MeetingListItemResponse,
  type MeetingProcessResponse,
  type MeetingResultData,
} from "@/lib/api";
import { MeetingResults } from "./meeting-results";
import { MeetingUploadForm } from "./meeting-upload-form";
import { RecentMeetings } from "./recent-meetings";

export function MeetingDashboard() {
  const [meetings, setMeetings] = useState<MeetingListItemResponse[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
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

  async function selectMeeting(meeting: MeetingListItemResponse) {
    if (meeting.status !== "completed") return;
    try {
      setHistoryError(null);
      const stored = await getMeeting(meeting.id);
      if (!stored.analysis || !stored.transcript) {
        setHistoryError("This meeting does not have a complete stored result.");
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
      setHistoryError("Could not load this meeting.");
    }
  }

  function handleProcessed(processed: MeetingProcessResponse) {
    setSelectedId(processed.meeting_id);
    setResult(processed);
    setIsHistoryLoading(true);
    void refreshMeetings();
  }

  return (
    <>
      <MeetingUploadForm onProcessed={handleProcessed} />
      <RecentMeetings
        meetings={meetings}
        isLoading={isHistoryLoading}
        error={historyError}
        selectedId={selectedId}
        onSelect={selectMeeting}
      />
      {result && <MeetingResults result={result} />}
    </>
  );
}
