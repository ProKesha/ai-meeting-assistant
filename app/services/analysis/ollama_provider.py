import httpx

from app.models.analysis import MeetingAnalysis
from app.services.ollama import (
    OllamaChatClient,
    OllamaInvalidResponseError,
    OllamaUnavailableError,
)

SYSTEM_PROMPT = """You analyze meeting transcripts into concise structured results.

Preserve the transcript's factual meaning and names exactly as stated. Do not invent facts,
assignees, deadlines, decisions, tasks, or questions. Do not change future events into past
events. Use null when an assignee or deadline is unknown. Include only explicit decisions and
explicit action items. Include only questions that are explicitly present or clearly unresolved
in the transcript. Use medium priority unless urgency is clearly stated; a deadline alone does
not make an item high priority. Summarize concisely.

Return ONLY the final structured response matching the provided schema. Do not output reasoning,
analysis, or chain-of-thought. Do not place the answer in a thinking or reasoning field. Emit the
complete structured response as the assistant's final content.
"""


class OllamaAnalysisProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._chat_client = OllamaChatClient(
            base_url=base_url,
            model=model,
            client=client,
        )

    @property
    def model(self) -> str:
        return self._chat_client.model

    def analyze(self, transcript: str) -> MeetingAnalysis:
        return self._chat_client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                "Analyze the meeting transcript below. Return ONLY the final structured "
                "response matching the provided schema in the assistant's final content. "
                "Do not output reasoning or place the answer in a thinking field.\n\n"
                f"Transcript:\n{transcript}"
            ),
            response_model=MeetingAnalysis,
        )
