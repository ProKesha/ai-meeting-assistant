import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.models import MeetingRecord
from app.db.session import get_db_session
from app.models.analysis import MeetingAnalysisRequest, MeetingAnalysisResponse
from app.models.meeting import (
    AudioUploadResponse,
    MeetingCreate,
    MeetingDetailResponse,
    MeetingListItemResponse,
    MeetingResponse,
    TranscriptionRequest,
    TranscriptionResponse,
)
from app.models.processing import MeetingProcessRequest, MeetingProcessResponse
from app.repositories.meetings import MeetingRepository, analysis_from_record
from app.services.audio_storage import (
    AudioFileTooLargeError,
    AudioStorage,
    EmptyAudioFileError,
    UnsupportedAudioExtensionError,
    get_audio_storage,
)
from app.services.analysis import (
    AnalysisService,
    AnalysisServiceInvalidResponseError,
    AnalysisServiceUnavailableError,
    get_analysis_service,
)
from app.services.transcription import (
    TranscriptionService,
    TranscriptionServiceError,
    TranscriptionServiceUnavailableError,
    get_transcription_service,
)
from app.services.meeting_processing import (
    InvalidMeetingAudioFilenameError,
    MeetingAudioNotFoundError,
    MeetingProcessingService,
)

router = APIRouter(prefix="/api/v1/meetings", tags=["meetings"])
logger = logging.getLogger(__name__)


async def attempt_mark_failed(
    repository: MeetingRepository,
    meeting: MeetingRecord,
) -> None:
    try:
        await repository.set_status(meeting, "failed")
    except Exception:
        logger.exception("Could not persist failed status for meeting %s", meeting.id)
        try:
            await repository.session.rollback()
        except Exception:
            logger.exception("Could not roll back failed status update")


def get_meeting_processing_service(
    audio_storage: AudioStorage = Depends(get_audio_storage),
    transcription_service: TranscriptionService = Depends(get_transcription_service),
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> MeetingProcessingService:
    return MeetingProcessingService(
        audio_storage=audio_storage,
        transcription_service=transcription_service,
        analysis_service=analysis_service,
    )


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    meeting: MeetingCreate,
    session: AsyncSession = Depends(get_db_session),
) -> MeetingResponse:
    record = await MeetingRepository(session).create(meeting)
    return MeetingResponse(
        id=record.id,
        title=record.title,
        description=record.description,
        status=record.status,
    )


@router.get("", response_model=list[MeetingListItemResponse])
async def list_meetings(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[MeetingListItemResponse]:
    records = await MeetingRepository(session).list(limit=limit, offset=offset)
    return [
        MeetingListItemResponse(
            id=record.id,
            title=record.title,
            status=record.status,
            created_at=record.created_at,
            summary=record.summary,
        )
        for record in records
    ]


@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
async def get_meeting(
    meeting_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MeetingDetailResponse:
    record = await MeetingRepository(session).get(meeting_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    return MeetingDetailResponse(
        id=record.id,
        title=record.title,
        description=record.description,
        status=record.status,
        audio_filename=record.audio_filename,
        transcript=record.transcript,
        analysis=analysis_from_record(record),
        transcription_model=record.transcription_model,
        analysis_model=record.analysis_model,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post(
    "/{meeting_id}/audio",
    response_model=AudioUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_meeting_audio(
    meeting_id: UUID,
    file: UploadFile = File(...),
    audio_storage: AudioStorage = Depends(get_audio_storage),
    session: AsyncSession = Depends(get_db_session),
) -> AudioUploadResponse:
    repository = MeetingRepository(session)
    meeting = await repository.get(meeting_id)
    if meeting is None:
        await file.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    try:
        stored_audio = await audio_storage.save(meeting_id, file)
    except UnsupportedAudioExtensionError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    except EmptyAudioFileError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AudioFileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)) from exc
    finally:
        await file.close()

    await repository.mark_uploaded(meeting, stored_audio.filename)

    return AudioUploadResponse(
        meeting_id=meeting_id,
        filename=stored_audio.filename,
        content_type=file.content_type,
        size_bytes=stored_audio.size_bytes,
        status="uploaded",
    )


@router.post(
    "/{meeting_id}/transcribe",
    response_model=TranscriptionResponse,
    status_code=status.HTTP_200_OK,
)
def transcribe_meeting_audio(
    meeting_id: UUID,
    request: TranscriptionRequest,
    audio_storage: AudioStorage = Depends(get_audio_storage),
    transcription_service: TranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResponse:
    try:
        audio_path = audio_storage.resolve(meeting_id, request.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid audio filename") from exc

    if not audio_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found")

    try:
        transcription = transcription_service.transcribe(audio_path)
    except TranscriptionServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription service unavailable",
        ) from exc
    except TranscriptionServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed",
        ) from exc

    return TranscriptionResponse(
        meeting_id=meeting_id,
        text=transcription.text,
        model=transcription.model,
        status="completed",
    )


@router.post(
    "/{meeting_id}/analyze",
    response_model=MeetingAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_meeting_transcript(
    meeting_id: UUID,
    request: MeetingAnalysisRequest,
    analysis_service: AnalysisService = Depends(get_analysis_service),
) -> MeetingAnalysisResponse:
    try:
        result = analysis_service.analyze(request.transcript)
    except AnalysisServiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local analysis service unavailable",
        ) from exc
    except AnalysisServiceInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from analysis service",
        ) from exc

    return MeetingAnalysisResponse(
        meeting_id=meeting_id,
        analysis=result.analysis,
        model=result.model,
        status="completed",
    )


@router.post(
    "/{meeting_id}/process",
    response_model=MeetingProcessResponse,
    status_code=status.HTTP_200_OK,
)
async def process_meeting(
    meeting_id: UUID,
    request: MeetingProcessRequest,
    processing_service: MeetingProcessingService = Depends(get_meeting_processing_service),
    session: AsyncSession = Depends(get_db_session),
) -> MeetingProcessResponse:
    repository = MeetingRepository(session)
    meeting = await repository.get(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    await repository.set_status(meeting, "processing")

    try:
        result = await run_in_threadpool(processing_service.process, meeting_id, request.filename)
    except InvalidMeetingAudioFilenameError as exc:
        await attempt_mark_failed(repository, meeting)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid audio filename",
        ) from exc
    except MeetingAudioNotFoundError as exc:
        await attempt_mark_failed(repository, meeting)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        ) from exc
    except TranscriptionServiceUnavailableError as exc:
        await attempt_mark_failed(repository, meeting)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Transcription service unavailable",
        ) from exc
    except TranscriptionServiceError as exc:
        await attempt_mark_failed(repository, meeting)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed",
        ) from exc
    except AnalysisServiceUnavailableError as exc:
        await attempt_mark_failed(repository, meeting)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local analysis service unavailable",
        ) from exc
    except AnalysisServiceInvalidResponseError as exc:
        await attempt_mark_failed(repository, meeting)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Invalid response from analysis service",
        ) from exc

    await repository.persist_processing_result(meeting, result)

    return MeetingProcessResponse(
        meeting_id=meeting_id,
        transcript=result.transcript,
        analysis=result.analysis,
        transcription_model=result.transcription_model,
        analysis_model=result.analysis_model,
        status="completed",
    )
