import asyncio
import os
from pathlib import Path
from src.defensive_architect import DefensiveArchitectAgent

async def main():
    agent = DefensiveArchitectAgent()
    blueprint_path = "/Users/jwalinshah/.gemini/antigravity-cli/brain/6861d738-7f66-41c7-8440-3180d48e51c2/odysseus_v2_blueprint.md"
    
    print(f"[*] Sending Blueprint to MiniMax-M3 for Hostile Review...")
    critique = await agent.review_staged_skill(blueprint_path)
    
    out_path = Path("data/skills_staging/v2_blueprint_critique.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(critique)
    
    print("\n--- MINIMAX-M3 CRITIQUE ---")
    print(critique)
    print(f"\n[+] Critique saved to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
