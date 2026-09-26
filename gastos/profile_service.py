QUESTION_WEIGHTS = {
    'records': 2,
    'update_frequency': 2,
    'monthly_volume': 1,
    'future_commitments': 2,
    'people_involved': 1,
    'predictability': 1,
    'management_need': 2,
    'advanced_controls': 2,
}


def level_for_score(score):
    if score <= 8:
        return 'essential'
    if score <= 18:
        return 'managerial'
    return 'complete'


def evaluate_maturity(answers):
    score = 0
    missing_weight = 0
    factors = []
    for key, weight in QUESTION_WEIGHTS.items():
        raw = answers.get(key)
        if raw in (None, '', 'unknown'):
            missing_weight += weight
            continue
        value = int(raw)
        score += value * weight
        if value == 2:
            factors.append(key)

    minimum_level = level_for_score(score)
    maximum_score = score + (missing_weight * 2)
    maximum_level = level_for_score(maximum_score)
    definitive = minimum_level == maximum_level
    recommended_level = minimum_level if definitive else ''
    inconsistencies = []
    if answers.get('advanced_controls') == '2' and score <= 8:
        inconsistencies.append('advanced_need_with_low_total')

    return {
        'score': score if not missing_weight else None,
        'calculated_score': score,
        'maximum_possible_score': maximum_score,
        'recommended_level': recommended_level,
        'is_boundary': definitive and score in {8, 9, 18, 19},
        'determining_factors': factors,
        'missing_answers': [key for key in QUESTION_WEIGHTS if answers.get(key) in (None, '', 'unknown')],
        'inconsistencies': inconsistencies,
        'definitive': definitive,
    }
