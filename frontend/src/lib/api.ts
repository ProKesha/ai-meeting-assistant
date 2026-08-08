const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type Priority = "low" | "medium" | "high";

export interface ActionItem {
  task: string;
  assignee: string | null;
  deadline: string | null;
  priority: Priority;
}

export interface MeetingAnalysis {
  summary: string;
  decisions: string[];
  action_items: ActionItem[];
  open_questions: string[];
}

export interface CreateMeetingRequest {
  title: string;
  description?: string;
}

export interface MeetingResponse {
  id: string;
  title: string;
  description: string | null;
  status: string;
}

export interface AudioUploadResponse {
  meeting_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  status: string;
}

export interface MeetingProcessResponse {
  meeting_id: string;
  transcript: string;
  analysis: MeetingAnalysis;
  transcription_model: string;
  analysis_model: string;
  status: "completed";
}

export interface MeetingDetailResponse {
  id: string;
  title: string;
  description: string | null;
  status: string;
  audio_filename: string | null;
  transcript: string | null;
  analysis: MeetingAnalysis | null;
  transcription_model: string | null;
  analysis_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface MeetingListItemResponse {
  id: string;
  title: string;
  status: string;
  created_at: string;
  summary: string | null;
}

export interface MeetingResultData {
  transcript: string;
  analysis: MeetingAnalysis;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // A stage-specific safe message is shown if the response body is not JSON.
    }
    throw new ApiError(detail, response.status);
  }

  return (await response.json()) as T;
}

export function createMeeting(input: CreateMeetingRequest): Promise<MeetingResponse> {
  return requestJson<MeetingResponse>("/api/v1/meetings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: input.title,
      description: input.description?.trim() || null,
    }),
  });
}

export function uploadMeetingAudio(
  meetingId: string,
  file: File,
): Promise<AudioUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson<AudioUploadResponse>(`/api/v1/meetings/${meetingId}/audio`, {
    method: "POST",
    body: formData,
  });
}

export function processMeeting(
  meetingId: string,
  filename: string,
): Promise<MeetingProcessResponse> {
  return requestJson<MeetingProcessResponse>(`/api/v1/meetings/${meetingId}/process`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
}

export function getMeetings(
  limit = 10,
  offset = 0,
): Promise<MeetingListItemResponse[]> {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return requestJson<MeetingListItemResponse[]>(`/api/v1/meetings?${query}`, {
    method: "GET",
  });
}

export function getMeeting(meetingId: string): Promise<MeetingDetailResponse> {
  return requestJson<MeetingDetailResponse>(`/api/v1/meetings/${meetingId}`, {
    method: "GET",
  });
}
