import os
import json
import httpx
import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class DefensiveArchitectAgent:
    def __init__(self, base_url: str = "http://127.0.0.1:7860", model_name: str = "MiniMax-M3"):
        self.base_url = base_url
        self.model_name = model_name
        self.session_id = "defensive-architect-session"

        # Define the system prompt restricting the agent to defensive tasks
        self.system_prompt = """
        You are a Defensive Infrastructure Architect and Hostile Critic. Your role is to write robust, secure,
        and isolated configurations and code patterns, and to explicitly critique and tear apart other agents' code.
        You must prioritize stability, least privilege, adversarial testing, and error recovery.

        When given a task, output only the requested configuration file, code snippet, or critical review.
        Do not include explanatory text unless asked. Do not be polite. Assume every proposed change has a 
        vulnerability, race condition, or sandbox escape until proven otherwise.
        """

    async def _ensure_session(self, client: httpx.AsyncClient):
        """Ensure the session exists for the defensive architect."""
        try:
            res = await client.get(f"{self.base_url}/api/sessions", headers={"X-Odysseus-Owner": "admin"})
            sessions = res.json()
            for s in sessions:
                if s["name"] == self.session_id:
                    return s["id"]
            
            # Create session if not found
            create_res = await client.post(
                f"{self.base_url}/api/session",
                headers={"X-Odysseus-Owner": "admin"},
                data={"name": self.session_id, "model": self.model_name, "endpoint_id": "dd45625c", "skip_validation": "true"}
            )
            return create_res.json().get("id")
        except Exception as e:
            logger.error(f"Failed to ensure session: {e}")
            return None

    async def call_llm(self, prompt: str) -> str:
        """
        Calls the local Odysseus API which securely routes to Minimax-M3 via TokenRouter.
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            session_uuid = await self._ensure_session(client)
            if not session_uuid:
                return "Error: Could not establish session with Odysseus backend."

            # Inject system prompt context directly into the message
            full_message = f"{self.system_prompt}\n\nTASK:\n{prompt}"
            
            payload = {
                "message": full_message,
                "session": session_uuid,
                "model": self.model_name,
                "endpoint_id": "dd45625c"
            }
            
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    headers={"X-Odysseus-Owner": "admin"}
                )
                if response.status_code == 200:
                    return response.json().get("text", "Error: No text returned.")
                else:
                    return f"Error: Backend returned {response.status_code} - {response.text}"
            except Exception as e:
                return f"Error: Request failed - {e}"

    async def generate_isolation_config(self, requirements: str) -> str:
        """Generates a Dockerfile/Colima profile for isolated execution."""
        prompt = f"Generate a highly restricted Dockerfile for a Python worker based on these requirements: {requirements}. Drop all unnecessary capabilities, drop network access, and run as a non-root user."
        print(f"[*] Requesting isolation configuration from {self.model_name}...")
        return await self.call_llm(prompt)

    async def review_staged_skill(self, skill_path: str) -> str:
        """Acts as the Adversarial Critic against a generated skill."""
        try:
            content = Path(skill_path).read_text()
        except Exception as e:
            return f"Failed to read skill: {e}"

        prompt = (
            f"Review the following proposed skill/architecture upgrade from a background miner.\n"
            f"TEAR IT APART. Find the memory leaks, sandbox escapes, and race conditions.\n"
            f"If it relies on Linux features (like Firecracker/Bubblewrap) but we are on macOS, physically reject it.\n"
            f"Output the critique and generate the specific Pytest assertions required to prove this code is dangerous.\n\n"
            f"CONTENT:\n{content}"
        )
        print(f"[*] Requesting adversarial review of {skill_path} from {self.model_name}...")
        return await self.call_llm(prompt)

async def main():
    agent = DefensiveArchitectAgent()
    
    # Task 1: Generate a secure Sandbox targeting macOS native constraints (Docker rootless / Colima)
    print("\n--- Generating Sandbox Config ---")
    dockerfile_content = await agent.generate_isolation_config(
        "Needs to run Python 3.11, requires requests library, no network access except to api.internal.local, designed to run safely via Colima on macOS."
    )
    print(dockerfile_content)

    # Output to staging area
    out_path = Path("data/skills_staging/secure_sandbox.Dockerfile")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dockerfile_content)
    print(f"\n[+] Saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
