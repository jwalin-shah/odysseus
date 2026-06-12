#!/bin/bash
# Batch Miner Script for Odysseus V2
# Loops over all project documents and routes them through the V2 CLI.
# The router inherently acts as a Latent MoE (falling back across models based on live quotas).

# Ensure the V2 CLI environment is accessible
V2_BIN="/Users/jwalinshah/projects/odysseus/v2/.venv/bin"
ROUTER="${V2_BIN}/ody-router"

# Create output directory for generated code/summaries
OUT_DIR="/Users/jwalinshah/projects/odysseus/v2/data/mining_output"
mkdir -p "$OUT_DIR"

echo "=============================================="
echo "🚀 Starting Latent MoE Batch Miner..."
echo "Target Model: minimax-m3 (Fallback: Waterfall)"
echo "=============================================="

# Find all markdown files in the original Odysseus context
for doc in /Users/jwalinshah/projects/odysseus/docs/*.md; do
    if [ ! -f "$doc" ]; then
        echo "No documents found to mine. Skipping."
        break
    fi
    
    filename=$(basename "$doc")
    echo "[*] Mining document: $filename"
    
    # Send the document through the router
    # Send the document through the router explicitly targeting minimax-m3 for maximum free compute
    cat "$doc" | "$ROUTER" --model minimax-m3 >> "${OUT_DIR}/extracted_${filename}"
    
    # Check if the router hit a quota exhaustion
    if [ $? -eq 75 ]; then
        echo "❌ CRITICAL: Latent MoE ran out of quota entirely (Exit 75). Stopping batch miner."
        exit 75
    fi
    
    echo "✅ Successfully routed $filename"
    sleep 1 # Small delay to respect rate limits
done

echo "=============================================="
echo "🎉 Batch Mining Complete. Outputs saved to $OUT_DIR"
echo "=============================================="
