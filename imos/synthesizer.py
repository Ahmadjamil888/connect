from __future__ import annotations

from imos.models import IMOSResult, IMOSTask


class ResultSynthesizer:
    def __init__(self, model_adapter=None) -> None:
        self.model_adapter = model_adapter

    async def synthesize_results(self, results: list[IMOSResult]) -> str:
        if not results:
            return ""
        if len(results) == 1:
            single = results[0]
            return str(single.output if single.output is not None else single.error or "")
        if self.model_adapter:
            prompt = "Synthesize these IMOS task results into one coherent response.\n\n"
            for item in results:
                content = item.output if item.success else item.error
                prompt += f"- [{item.adapter_name}] success={item.success}: {content}\n"
            response = await self.model_adapter.send(
                IMOSTask(
                    task_id="synthesis",
                    prompt=prompt,
                    subtask_type="question_answer",
                    target_adapter=self.model_adapter.name,
                    metadata={"system_prompt": "Summarize action outputs clearly. Format code as fenced blocks and actions as bullets."},
                )
            )
            if response.success:
                return str(response.output)
        lines = []
        for item in results:
            content = item.output if item.success else item.error
            if isinstance(content, str) and ("\n" in content or "def " in content):
                lines.append(f"- {item.adapter_name}:\n```text\n{content}\n```")
            else:
                lines.append(f"- {item.adapter_name}: {content}")
        return "\n".join(lines)
