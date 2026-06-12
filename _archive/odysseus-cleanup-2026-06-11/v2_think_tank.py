import asyncio
from src.defensive_architect import DefensiveArchitectAgent

async def main():
    agent = DefensiveArchitectAgent()
    
    ideas = """
    PROPOSED V2 ARCHITECTURE CONCEPTS:
    1. THE AST REPOMAP: We will use native Tree-sitter to parse Python ASTs. We will inject this graph as a text blob at the top of the LLM context for every request.
    2. THE CONTEXT MANAGER: We will use a local Vector Database (ChromaDB) to store transcript teachings. Before an agent acts, it queries ChromaDB for similar past tasks and injects the top 3 results into its prompt.
    3. NATIVE CLIs: We will abandon MCP daemons. Every tool will be a stateless Python CLI (e.g., `ody-map`, `ody-quota`) that prints JSON to stdout and terminates.
    """
    
    print("[*] Forcing MiniMax-M3 to break the V2 Architecture...")
    prompt = f"TEAR THESE CONCEPTS APART. Find the exact ways these 3 ideas will cause context blowouts, memory leaks, or logical failures in a production coding agent. DO NOT BE POLITE.\n\n{ideas}"
    
    critique = await agent.call_llm(prompt)
    print("\n--- MINIMAX-M3 DESTRUCTION REPORT ---")
    print(critique)

if __name__ == "__main__":
    asyncio.run(main())
