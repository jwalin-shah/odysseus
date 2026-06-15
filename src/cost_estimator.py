from typing import Dict, Tuple


def sum_tokens_by_model(trajectory_log: list) -> Dict[str, Tuple[int, int]]:
    result: Dict[str, Tuple[int, int]] = {}
    for step in trajectory_log:
        model = step['model']
        input_tokens = step['input_tokens']
        output_tokens = step['output_tokens']
        
        if model in result:
            current_input, current_output = result[model]
            result[model] = (current_input + input_tokens, current_output + output_tokens)
        else:
            result[model] = (input_tokens, output_tokens)
    
    return result
