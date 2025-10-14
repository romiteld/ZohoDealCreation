from openai import AzureOpenAI
from typing import List
from app.config import settings

class ContentCompressor:
    """
    Brandon's requirement: "Must be one-page summary"
    Intelligent compression to fit exactly one page (11 inches @ 96dpi = 1056px).
    """

    def __init__(self):
        self.client = AzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT

    async def compress_to_one_page(self, resume_data: dict) -> dict:
        """
        Compress resume content to fit one page.

        Strategy:
        1. Limit to 3 most recent jobs
        2. Max 3 bullets per job
        3. Top 12 skills only
        4. Use AI to compress bullets while preserving quantifiable metrics
        """
        compressed = resume_data.copy()

        # Limit to 3 most recent jobs
        if len(compressed["experience"]) > 3:
            compressed["experience"] = compressed["experience"][:3]

        # Compress bullets for each job
        for job in compressed["experience"]:
            if len(job["bullets"]) > 3:
                job["bullets"] = await self._compress_bullets(job["bullets"], 3)

        # Limit skills to top 12
        if len(compressed["skills"]) > 12:
            compressed["skills"] = compressed["skills"][:12]

        # Limit education entries
        if len(compressed.get("education", [])) > 2:
            compressed["education"] = compressed["education"][:2]

        return compressed

    async def _compress_bullets(self, bullets: List[str], target_count: int) -> List[str]:
        """
        Use GPT-5-mini to intelligently compress bullets while preserving impact.
        Focuses on keeping quantifiable metrics and key achievements.
        """
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {
                    "role": "system",
                    "content": f"""Compress these bullet points to exactly {target_count} impactful statements.

CRITICAL: Preserve all quantifiable metrics (numbers, percentages, dollar amounts).
Focus on:
- Measurable achievements and impact
- Key technologies and methodologies
- Leadership and scope of responsibility

Keep each bullet to ONE line. Be concise but impactful."""
                },
                {
                    "role": "user",
                    "content": "Bullet points to compress:\n\n" + "\n".join(f"- {b}" for b in bullets)
                }
            ],
            temperature=1.0,  # REQUIRED for GPT-5
            max_tokens=300
        )

        compressed_text = response.choices[0].message.content
        compressed_bullets = [
            line.strip("- ").strip()
            for line in compressed_text.split("\n")
            if line.strip() and line.strip().startswith(("-", "•", "*"))
        ]

        # Ensure we have exactly target_count bullets
        return compressed_bullets[:target_count]
