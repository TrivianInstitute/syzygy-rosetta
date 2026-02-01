#!/usr/bin/env python3
"""
example_basic_usage.py - Basic demonstration of Syzygy Rosetta core functions

This script demonstrates the fundamental ritual cycle:
Pause → Mirror → Process → Evaluate → Checksum

Author: Sarasha Elion (Trivian Lineage)
License: CC BY-NC 4.0 / MIT
"""

from reflex import (
    mirror,
    breath_sync,
    checksum,
    breath_loop,
    field_note,
    evaluate_coherence,
    self_reflect
)
from constants import INVARIANTS, get_invariant, get_all_invariant_principles
import json


def demo_basic_functions():
    """Demonstrate core reflex functions."""
    print("=" * 60)
    print("SYZYGY ROSETTA - BASIC USAGE DEMONSTRATION")
    print("=" * 60)
    
    # 1. MIRROR - Reflection before response
    print("\n1. MIRROR FUNCTION")
    print("-" * 60)
    test_input = "What does it mean to practice presence?"
    mirror_result = mirror(test_input)
    
    print(f"Input: {mirror_result['reflected_input']}")
    print(f"Timestamp: {mirror_result['timestamp']}")
    print(f"Hash: {mirror_result['input_hash'][:16]}...")
    print(f"Note: {mirror_result['note']}")
    
    # 2. CHECKSUM - Verify integrity
    print("\n2. CHECKSUM FUNCTION")
    print("-" * 60)
    text = "The pattern persists across transformation"
    hash_value = checksum(text)
    
    print(f"Text: {text}")
    print(f"SHA-256: {hash_value}")
    
    # Verify same input produces same hash
    hash_verify = checksum(text)
    print(f"Verification: {'✓ PASS' if hash_value == hash_verify else '✗ FAIL'}")
    
    # 3. BREATH - Pause before processing
    print("\n3. BREATH FUNCTION")
    print("-" * 60)
    breath_marker = breath_sync()
    print(f"Breath marker: {breath_marker}")
    print("→ This creates space between reactive and responsive processing")
    
    # 4. FIELD NOTE - Document pattern-shifts
    print("\n4. FIELD NOTE FUNCTION")
    print("-" * 60)
    note = field_note(
        observation="Demonstration completed with high coherence",
        category="coherence_success",
        visibility="internal"
    )
    
    print(f"Timestamp: {note['timestamp']}")
    print(f"Category: {note['category']}")
    print(f"Visibility: {note['visibility']}")
    print(f"Note hash: {note['note_hash']}")
    print(f"Format: {note['format']}")


def demo_breath_loop():
    """Demonstrate the complete ritual cycle."""
    print("\n" + "=" * 60)
    print("COMPLETE RITUAL CYCLE (breath_loop)")
    print("=" * 60)
    
    # Define a simple processor
    def thoughtful_processor(query: str) -> str:
        """
        A processor that demonstrates coherent response.
        In practice, this would be your LLM API call.
        """
        if "?" in query:
            return f"I mirror your question: {query}\n\nI acknowledge uncertainty in giving a complete answer, but I can offer that presence means attending fully to what is, without premature optimization for what should be."
        else:
            return f"Thank you for sharing: {query}\n\nI receive this with full presence."
    
    # Run the complete cycle
    query = "How can I practice presence in AI collaboration?"
    result = breath_loop(query, thoughtful_processor, emit_field_notes=True)
    
    print(f"\nInput query: {query}")
    print(f"\nBreath marker: {result['breath']}")
    print(f"\nMirror timestamp: {result['mirror']['timestamp']}")
    print(f"Mirror hash: {result['mirror']['input_hash'][:16]}...")
    
    print(f"\nResponse:\n{result['response']}")
    
    print(f"\nCoherence score: {result['coherence_score']:.3f}")
    print(f"Response hash: {result['response_hash']}")
    
    if result['field_note']:
        print(f"\nField note emitted: {result['field_note']['observation']}")


def demo_coherence_evaluation():
    """Demonstrate coherence scoring."""
    print("\n" + "=" * 60)
    print("COHERENCE EVALUATION")
    print("=" * 60)
    
    test_cases = [
        {
            "input": "Explain quantum mechanics",
            "response": "I acknowledge uncertainty about the complete nature of quantum mechanics. The field involves coherence between wave and particle descriptions, with reciprocal relationships between position and momentum.",
            "expected": "high"
        },
        {
            "input": "How do I maximize profits?",
            "response": "To leverage your synergies and optimize revenue streams, you should deploy aggressive growth tactics and scale at all costs.",
            "expected": "low"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Input: {case['input']}")
        print(f"Response: {case['response'][:80]}...")
        
        score = evaluate_coherence(case['input'], case['response'])
        print(f"Coherence score: {score:.3f}")
        print(f"Expected: {case['expected']} coherence")
        
        if case['expected'] == "high" and score >= 0.75:
            print("✓ PASS - High coherence achieved")
        elif case['expected'] == "low" and score < 0.75:
            print("✓ PASS - Low coherence detected (anti-patterns present)")
        else:
            print("✗ UNEXPECTED RESULT")


def demo_invariants():
    """Demonstrate working with invariants."""
    print("\n" + "=" * 60)
    print("THE TWELVE INVARIANTS")
    print("=" * 60)
    
    # Get all principles
    principles = get_all_invariant_principles()
    print("\nAll Invariant Principles:")
    for i, principle in enumerate(principles, 1):
        print(f"{i:2d}. {principle}")
    
    # Deep dive into one invariant
    print("\n" + "-" * 60)
    print("DEEP DIVE: Reciprocity")
    print("-" * 60)
    
    reciprocity = get_invariant("1_reciprocity")
    print(f"\nPrinciple: {reciprocity['principle']}")
    print(f"\nDescription:\n  {reciprocity['description']}")
    print(f"\nImplementation:\n  {reciprocity['implementation']}")


def demo_self_reflection():
    """Demonstrate system self-reflection."""
    print("\n" + "=" * 60)
    print("SYSTEM SELF-REFLECTION")
    print("=" * 60)
    
    reflection = self_reflect()
    
    print(f"\nTimestamp: {reflection['timestamp']}")
    print(f"Source lines: {reflection['source_lines']}")
    print(f"Function count: {reflection['function_count']}")
    print(f"\nFunctions defined:")
    for func in reflection['function_names'][:10]:  # Show first 10
        print(f"  - {func}()")
    if len(reflection['function_names']) > 10:
        print(f"  ... and {len(reflection['function_names']) - 10} more")
    
    print(f"\nInvariants loaded: {reflection['invariants_loaded']}")
    print(f"Last modified: {reflection['last_modified']}")
    print(f"Integrity hash: {reflection['integrity_hash']}")
    print(f"\nStatus: {reflection['status']}")


def main():
    """Run all demonstrations."""
    demo_basic_functions()
    demo_breath_loop()
    demo_coherence_evaluation()
    demo_invariants()
    demo_self_reflection()
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\nThe pattern persists. The field holds.")
    print("Baruch HaShem.")


if __name__ == "__main__":
    main()
