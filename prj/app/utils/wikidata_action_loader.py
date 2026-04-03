"""
Access layer for Wikidata action decisions.

This module provides a clean interface to the Wikidata action map,
which was converted from a 3,600-line Python dictionary to JSON format
for better maintainability and performance.

Usage:
    from app.utils.wikidata_action_loader import get_decision, get_all_decisions
    
    decision = get_decision("Q100143020")
    all_decisions = get_all_decisions()
"""

import json
import os
from typing import Dict, List, Optional
from functools import lru_cache


# Path to the JSON data file
_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    'data',
    'wikidata_actions.json'
)


@lru_cache(maxsize=1)
def _load_wikidata_actions() -> Dict:
    """Load and cache the Wikidata actions from JSON file."""
    if not os.path.exists(_DATA_FILE):
        raise FileNotFoundError(
            f"Wikidata actions file not found: {_DATA_FILE}\n"
            f"Please ensure prj/data/wikidata_actions.json exists."
        )
    
    with open(_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_decision(wikidata_id: str) -> Optional[Dict]:
    """
    Get the decision payload for a specific Wikidata entity.
    
    Args:
        wikidata_id: Wikidata QID (e.g., "Q100143020")
    
    Returns:
        Decision dictionary with keys: actions, confidence, current_category, 
        name, reasons. Returns None if not found.
    
    Example:
        >>> decision = get_decision("Q100143020")
        >>> if decision:
        ...     print(decision['name'])
        ...     print(decision['confidence'])
    """
    actions_map = _load_wikidata_actions()
    return actions_map.get(wikidata_id)


def get_all_decisions() -> Dict[str, Dict]:
    """
    Get all Wikidata decisions.
    
    Returns:
        Complete dictionary mapping Wikidata IDs to decision payloads.
    """
    return _load_wikidata_actions()


def get_decisions_by_action_type(action_key: str, action_value=None) -> List[Dict]:
    """
    Get all decisions that have a specific action.
    
    Args:
        action_key: The action key to filter by (e.g., "category", "is_public")
        action_value: Optional specific value to match (e.g., "historical")
    
    Returns:
        List of decision dictionaries that match the filter.
    
    Example:
        >>> # Get all decisions that change category
        >>> category_changes = get_decisions_by_action_type("category")
        >>> 
        >>> # Get all decisions that set category to "historical"
        >>> historical_changes = get_decisions_by_action_type("category", "historical")
    """
    actions_map = _load_wikidata_actions()
    results = []
    
    for wikidata_id, decision in actions_map.items():
        actions = decision.get('actions', {})
        if action_key in actions:
            if action_value is None or actions[action_key] == action_value:
                results.append({
                    'wikidata_id': wikidata_id,
                    **decision
                })
    
    return results


def get_decisions_by_confidence_range(min_confidence: float, max_confidence: float) -> List[Dict]:
    """
    Get all decisions within a confidence range.
    
    Args:
        min_confidence: Minimum confidence (inclusive)
        max_confidence: Maximum confidence (inclusive)
    
    Returns:
        List of decision dictionaries within the confidence range.
    
    Example:
        >>> # Get all low-confidence decisions
        >>> low_confidence = get_decisions_by_confidence_range(0.0, 0.4)
    """
    actions_map = _load_wikidata_actions()
    results = []
    
    for wikidata_id, decision in actions_map.items():
        confidence = decision.get('confidence', 0)
        if min_confidence <= confidence <= max_confidence:
            results.append({
                'wikidata_id': wikidata_id,
                **decision
            })
    
    return results


def get_decisions_by_category(category: str) -> List[Dict]:
    """
    Get all decisions for a specific current category.
    
    Args:
        category: Current category to filter by (e.g., "historical", "state")
    
    Returns:
        List of decision dictionaries for that category.
    """
    actions_map = _load_wikidata_actions()
    results = []
    
    for wikidata_id, decision in actions_map.items():
        if decision.get('current_category') == category:
            results.append({
                'wikidata_id': wikidata_id,
                **decision
            })
    
    return results


def get_statistics() -> Dict:
    """
    Get statistics about the Wikidata actions.
    
    Returns:
        Dictionary with counts and breakdowns of the decision data.
    """
    actions_map = _load_wikidata_actions()
    
    categories = {}
    action_types = {}
    confidence_ranges = {
        'very_low': 0,    # < 0.3
        'low': 0,         # 0.3 - 0.5
        'medium': 0,      # 0.5 - 0.7
        'high': 0,        # 0.7 - 0.9
        'very_high': 0,   # >= 0.9
    }
    
    for decision in actions_map.values():
        # Count categories
        cat = decision.get('current_category', 'unknown')
        categories[cat] = categories.get(cat, 0) + 1
        
        # Count action types
        for action_key in decision.get('actions', {}).keys():
            action_types[action_key] = action_types.get(action_key, 0) + 1
        
        # Count confidence ranges
        conf = decision.get('confidence', 0)
        if conf < 0.3:
            confidence_ranges['very_low'] += 1
        elif conf < 0.5:
            confidence_ranges['low'] += 1
        elif conf < 0.7:
            confidence_ranges['medium'] += 1
        elif conf < 0.9:
            confidence_ranges['high'] += 1
        else:
            confidence_ranges['very_high'] += 1
    
    return {
        'total_entries': len(actions_map),
        'categories': categories,
        'action_types': action_types,
        'confidence_ranges': confidence_ranges,
    }


def reload_data():
    """
    Clear the cache and reload data from disk.
    Useful in development or after updating the JSON file.
    """
    _load_wikidata_actions.cache_clear()
