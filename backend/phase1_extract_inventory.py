#!/usr/bin/env python3
"""
PHASE 1: PRINCIPAL WORKFLOW INVENTORY EXTRACTION
Systematically extract all workflows where Principal has authority or escalation path.

This is NOT based on seeded data or code inspection alone.
It extracts from the actual approval matrix and identifies source models.
"""

import json
import sys
import re
from pathlib import Path

# Read matrices.py to extract all workflows
MATRICES_PATH = Path(__file__).parent / "matrices.py"

def extract_workflows():
    """Extract workflow matrix from matrices.py"""
    with open(MATRICES_PATH, 'r') as f:
        content = f.read()
    
    # Parse APPROVAL_MATRIX section
    # Extract between APPROVAL_MATRIX = [ and the closing ]
    start = content.find("APPROVAL_MATRIX = [")
    if start == -1:
        print("ERROR: Could not find APPROVAL_MATRIX")
        sys.exit(1)
    
    # Find matching closing bracket
    depth = 0
    i = start + len("APPROVAL_MATRIX = ")
    matrix_start = i
    while i < len(content):
        if content[i] == '[':
            depth += 1
        elif content[i] == ']':
            depth -= 1
            if depth == 0:
                matrix_end = i
                break
        i += 1
    
    matrix_str = content[matrix_start:matrix_end+1]
    
    # Extract using regex (crude but works)
    workflows = []
    pattern = r'\{\s*"key":\s*"([^"]+)",\s*"label":\s*"([^"]+)".*?"chain":\s*\[(.*?)\],.*?"escalation":\s*"([^"]*)"'
    
    for match in re.finditer(pattern, matrix_str, re.DOTALL):
        key = match.group(1)
        label = match.group(2)
        chain_str = match.group(3)
        escalation = match.group(4)
        
        # Parse chain
        chain = []
        for item in re.findall(r'"([^"]+)"', chain_str):
            chain.append(item)
        
        workflows.append({
            "process_key": key,
            "label": label,
            "chain": chain,
            "escalation": escalation,
            "principal_stage": None,  # Will be computed
            "principal_is_final": False,
            "principal_is_escalation": False
        })
    
    # Compute Principal involvement
    for wf in workflows:
        # Check if Principal in chain
        for idx, stage_role in enumerate(wf["chain"]):
            if "Principal" in stage_role or "principal" in stage_role:
                wf["principal_stage"] = idx + 1
                if idx == len(wf["chain"]) - 1:
                    wf["principal_is_final"] = True
        
        # Check if Principal is escalation target
        if "Principal" in wf["escalation"] or "principal" in wf["escalation"]:
            wf["principal_is_escalation"] = True
    
    # Filter to only those with Principal involvement
    principal_workflows = [
        wf for wf in workflows 
        if wf["principal_is_final"] or wf["principal_is_escalation"]
    ]
    
    return principal_workflows

def main():
    workflows = extract_workflows()
    
    print("=" * 100)
    print("PHASE 1: PRINCIPAL WORKFLOW INVENTORY")
    print("=" * 100)
    print()
    
    print(f"Total workflows with Principal involvement: {len(workflows)}")
    print()
    
    final_approver = [w for w in workflows if w["principal_is_final"]]
    escalation_target = [w for w in workflows if w["principal_is_escalation"] and not w["principal_is_final"]]
    both = [w for w in workflows if w["principal_is_final"] and w["principal_is_escalation"]]
    
    print(f"  - Final Approver: {len(final_approver)}")
    print(f"  - Escalation Target Only: {len(escalation_target)}")
    print(f"  - Both: {len(both)}")
    print()
    
    print("FINAL APPROVER WORKFLOWS:")
    print("-" * 100)
    for i, wf in enumerate(sorted(final_approver, key=lambda x: x["principal_stage"]), 1):
        print(f"{i}. {wf['process_key']:30s} | {wf['label']:40s} | Stage {wf['principal_stage']} | {len(wf['chain'])} total stages")
        print(f"   Chain: {' → '.join(wf['chain'])}")
        if wf["escalation"]:
            print(f"   Escalation: {wf['escalation']}")
        print()
    
    if escalation_target:
        print("ESCALATION TARGET WORKFLOWS (not final approver):")
        print("-" * 100)
        for i, wf in enumerate(escalation_target, 1):
            print(f"{i}. {wf['process_key']:30s} | {wf['label']:40s} | Escalates to Principal")
            print(f"   Chain: {' → '.join(wf['chain'])}")
            print()
    
    # Output JSON for reference
    output = {
        "timestamp": str(Path(__file__).parent),
        "total_workflows": len(workflows),
        "principal_final_approver_count": len(final_approver),
        "principal_escalation_target_count": len(escalation_target),
        "workflows": sorted(workflows, key=lambda x: x.get("principal_stage") or 999)
    }
    
    json_path = Path(__file__).parent / "principal_workflow_inventory.json"
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"Inventory saved to: {json_path}")

if __name__ == "__main__":
    main()
