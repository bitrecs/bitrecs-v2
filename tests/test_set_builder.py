import pytest
from unittest.mock import patch

from models.eval_type import BitrecsEvaluationType
from rules.set_builder import EvaluationSetBuilder

def test_derive_set_returns_set_with_fixed_elements():
    builder = EvaluationSetBuilder()
    result = builder.build_evaluation_set()
    assert isinstance(result, set)
    assert all(isinstance(item, BitrecsEvaluationType) for item in result)
    
    # Define fixed sets as per the function
    # screener_1 = {BitrecsEvaluationType.BITRECS_BASIC_DAILY}
    # screener_2 = {
    #     BitrecsEvaluationType.BITRECS_SAFE_DAILY,
    #     BitrecsEvaluationType.BITRECS_HAYSTACK_DAILY,
    #     BitrecsEvaluationType.BITRECS_QOS_DAILY,
    # }
    # validator_a = {
    #     BitrecsEvaluationType.BITRECS_PREDICT_DAILY,
    #     BitrecsEvaluationType.BITRECS_PROMPT_DAILY,
    #     BitrecsEvaluationType.BITRECS_REASON_DAILY,
    #     BitrecsEvaluationType.BITRECS_SKU_DAILY,
    # }
     
    screener_1 = builder.screener_1
    screener_2 = builder.screener_2
    validator_a = builder.validator_a
    fixed_union = screener_1 | screener_2 | validator_a
    fixed_union = screener_1 | screener_2 | validator_a
    
    # Assert all fixed elements are included
    assert fixed_union.issubset(result)
    
    # Assert total size is fixed size + 3 random
    expected_size = len(fixed_union) + 3
    assert len(result) == expected_size



@patch('rules.set_builder.secrets.choice') # Mocking secrets.choice  
def test_derive_set_with_mocked_random_selections(mock_choice):
    builder = EvaluationSetBuilder()    
    
    screener_1 = builder.screener_1
    screener_2 = builder.screener_2
    validator_a = builder.validator_a
    
    full_eval = set(BitrecsEvaluationType)
    pre_set = full_eval - screener_1 - screener_2 - validator_a
    
    # Mock secrets.choice to return specific items from pre_set
    mock_items = list(pre_set)[:3]  # Take first 3 for predictability
    mock_choice.side_effect = mock_items
    
    result = builder.build_evaluation_set()
    
    # Assert mocked items are included
    assert all(item in result for item in mock_items)
    
    # Assert fixed elements are still included
    fixed_union = screener_1 | screener_2 | validator_a
    assert fixed_union.issubset(result)
    
    # Assert no extra elements beyond fixed + mocked
    expected_result = fixed_union | set(mock_items)
    assert result == expected_result