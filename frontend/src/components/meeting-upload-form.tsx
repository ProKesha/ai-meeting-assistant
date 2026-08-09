"use client";

import { useRef, useState } from "react";
import type { DragEvent, FormEvent } from "react";
import {
  ApiError,
  createMeeting,
  processMeeting,
  uploadMeetingAudio,
  type MeetingProcessResponse,
} from "@/lib/api";
import { ProcessingState, type ProcessingStage } from "./processing-state";

const ALLOWED_EXTENSIONS = [".mp3", ".wav", ".m4a"];
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024;

function audioValidationMessage(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return "Choose an MP3, WAV, or M4A audio file.";
  }
  if (file.size === 0) return "Choose a recording that is not empty.";
  if (file.size > MAX_FILE_SIZE_BYTES) return "Choose a recording smaller than 50 MB.";
  return null;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function MeetingUploadForm({
  onProcessed,
}: {
  onProcessed: (result: MeetingProcessResponse) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [stage, setStage] = useState<ProcessingStage>("preparing");
  const [errors, setErrors] = useState<{ title?: string; audio?: string }>({});
  const [requestError, setRequestError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function selectFile(nextFile: File | null) {
    if (!nextFile || isProcessing) return;
    const message = audioValidationMessage(nextFile);
    if (message) {
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setErrors((current) => ({ ...current, audio: message }));
      return;
    }
    setFile(nextFile);
    setErrors((current) => ({ ...current, audio: undefined }));
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    selectFile(event.dataTransfer.files[0] ?? null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: { title?: string; audio?: string } = {};
    if (!title.trim()) nextErrors.title = "Enter a meeting title.";
    if (!file) nextErrors.audio = "Choose an audio file.";
    else nextErrors.audio = audioValidationMessage(file) ?? undefined;

    setErrors(nextErrors);
    if (nextErrors.title || nextErrors.audio || !file) return;

    setIsProcessing(true);
    setRequestError(null);
    let activeStage: ProcessingStage = "preparing";

    try {
      setStage("preparing");
      const meeting = await createMeeting({
        title: title.trim(),
        description: description.trim() || undefined,
      });

      activeStage = "uploading";
      setStage("uploading");
      const upload = await uploadMeetingAudio(meeting.id, file);

      activeStage = "processing";
      setStage("processing");
      const processed = await processMeeting(meeting.id, upload.filename);

      onProcessed(processed);
      setTitle("");
      setDescription("");
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setTimeout(() => {
        document.getElementById("meeting-results")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 50);
    } catch (error) {
      if (activeStage === "preparing") {
        setRequestError("Could not create meeting. Please try again.");
      } else if (activeStage === "uploading") {
        setRequestError("Could not upload audio. Please check the file and try again.");
      } else if (error instanceof ApiError && error.status === 503) {
        setRequestError("Local AI service is unavailable. Make sure it is running and try again.");
      } else {
        setRequestError("Meeting processing failed. Please try again.");
      }
    } finally {
      setIsProcessing(false);
    }
  }

  return (
    <>
      <section className="overflow-hidden rounded-3xl border border-[#dce3e6] bg-white shadow-[0_18px_55px_rgba(16,47,59,0.08)]">
        <div className="border-b border-[#e4e9eb] px-5 py-5 sm:px-7">
          <h2 className="text-lg font-semibold tracking-tight text-[#173540]">Upload meeting</h2>
          <p className="mt-1 text-sm text-[#74838a]">Add the details and recording. We’ll handle the rest.</p>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          <div className="grid gap-7 p-5 sm:p-7 lg:grid-cols-[1fr_0.92fr] lg:gap-9">
            <div className="space-y-5">
              <div>
                <label htmlFor="meeting-title" className="mb-2 block text-sm font-semibold text-[#294650]">
                  Meeting title <span className="text-[#b04b4b]">*</span>
                </label>
                <input
                  id="meeting-title"
                  value={title}
                  onChange={(event) => {
                    setTitle(event.target.value);
                    if (event.target.value.trim()) {
                      setErrors((current) => ({ ...current, title: undefined }));
                    }
                  }}
                  placeholder="e.g. Weekly product sync"
                  disabled={isProcessing}
                  aria-invalid={Boolean(errors.title)}
                  aria-describedby={errors.title ? "meeting-title-error" : undefined}
                  className="h-12 w-full rounded-xl border border-[#ccd6da] bg-white px-3.5 text-sm text-[#1d3c47] outline-none transition placeholder:text-[#9aa6ab] focus:border-[#397568] focus:ring-[3px] focus:ring-[#397568]/10 disabled:bg-[#f5f7f8]"
                />
                {errors.title && (
                  <p id="meeting-title-error" className="mt-1.5 text-xs font-medium text-[#a94b4b]">
                    {errors.title}
                  </p>
                )}
              </div>

              <div>
                <label htmlFor="meeting-description" className="mb-2 block text-sm font-semibold text-[#294650]">
                  Description <span className="font-normal text-[#8a979c]">(optional)</span>
                </label>
                <textarea
                  id="meeting-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="What was this meeting about?"
                  rows={5}
                  disabled={isProcessing}
                  className="w-full resize-none rounded-xl border border-[#ccd6da] bg-white px-3.5 py-3 text-sm leading-6 text-[#1d3c47] outline-none transition placeholder:text-[#9aa6ab] focus:border-[#397568] focus:ring-[3px] focus:ring-[#397568]/10 disabled:bg-[#f5f7f8]"
                />
              </div>

              <div className="hidden rounded-xl border border-[#e2e7e9] bg-[#f8fafb] p-4 text-sm text-[#687980] lg:block">
                <p className="font-semibold text-[#405963]">What you’ll get</p>
                <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
                  {["Concise summary", "Key decisions", "Action items", "Open questions"].map(
                    (item) => (
                      <span key={item} className="flex items-center gap-2">
                        <span className="h-1.5 w-1.5 rounded-full bg-[#4b8b7d]" />
                        {item}
                      </span>
                    ),
                  )}
                </div>
              </div>
            </div>

            <div>
              <label
                htmlFor="meeting-audio"
                className="mb-2 block text-sm font-semibold text-[#294650]"
              >
                Audio file <span className="text-[#b04b4b]">*</span>
              </label>
              <div
                onDragEnter={(event) => {
                  event.preventDefault();
                  setIsDragging(true);
                }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setIsDragging(false);
                  }
                }}
                onDrop={handleDrop}
                className={`flex min-h-[226px] flex-col items-center justify-center rounded-2xl border-2 border-dashed px-5 py-7 text-center transition ${
                  isDragging
                    ? "border-[#397568] bg-[#f1f8f6]"
                    : errors.audio
                      ? "border-[#d89b9b] bg-[#fffafa]"
                      : "border-[#cbd7da] bg-[#fafcfc] hover:border-[#86aaa2] hover:bg-[#f7faf9]"
                }`}
              >
                <input
                  ref={fileInputRef}
                  id="meeting-audio"
                  type="file"
                  accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4,audio/x-m4a"
                  onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
                  disabled={isProcessing}
                  className="sr-only"
                />

                {file ? (
                  <>
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[#e5f1ee] text-xl text-[#397568]" aria-hidden="true">
                      ♪
                    </div>
                    <p className="max-w-full truncate text-sm font-semibold text-[#294650]">{file.name}</p>
                    <p className="mt-1 text-xs text-[#829097]">{formatFileSize(file.size)}</p>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isProcessing}
                      className="mt-4 text-xs font-semibold text-[#397568] underline decoration-[#9bc1b8] underline-offset-4 hover:text-[#285b50]"
                    >
                      Choose a different file
                    </button>
                  </>
                ) : (
                  <>
                    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-[#d9e3e1] bg-white text-xl text-[#397568] shadow-sm" aria-hidden="true">
                      ↑
                    </div>
                    <p className="text-sm font-semibold text-[#294650]">Drop your recording here</p>
                    <p className="mt-1 text-xs text-[#829097]">or choose a file from your computer</p>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isProcessing}
                      className="mt-4 rounded-lg border border-[#c8d7d3] bg-white px-3.5 py-2 text-xs font-semibold text-[#397568] shadow-sm transition hover:border-[#86aaa2] hover:bg-[#f5faf8] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#397568]"
                    >
                      Browse files
                    </button>
                  </>
                )}
              </div>
              <div className="mt-2 flex items-start justify-between gap-4 text-xs">
                <p className={errors.audio ? "font-medium text-[#a94b4b]" : "text-[#829097]"}>
                  {errors.audio ?? "Supported formats: MP3, WAV, M4A"}
                </p>
                <p className="shrink-0 text-[#9aa6ab]">Max 50 MB</p>
              </div>
            </div>
          </div>

          <div className="border-t border-[#e4e9eb] bg-[#fbfcfc] px-5 py-5 sm:px-7">
            {isProcessing ? (
              <ProcessingState stage={stage} />
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-[#7b898f]">Processing time depends on recording length.</p>
                <button
                  type="submit"
                  className="inline-flex h-12 items-center justify-center rounded-xl bg-[#123a4a] px-6 text-sm font-semibold text-white shadow-[0_5px_15px_rgba(18,58,74,0.2)] transition hover:bg-[#0d2f3d] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#397568] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Process meeting
                  <span className="ml-2 text-base" aria-hidden="true">→</span>
                </button>
              </div>
            )}

            {requestError && !isProcessing && (
              <div className="mt-4 rounded-xl border border-[#ebcaca] bg-[#fff4f4] px-4 py-3 text-sm text-[#914545]" role="alert">
                {requestError}
              </div>
            )}
          </div>
        </form>
      </section>

    </>
  );
}
