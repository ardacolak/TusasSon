from typing import Dict, Any


ANGLE_ORDER = [0, 45, -45, 90]
ANGLE_LABELS = {0: "0°", 45: "+45°", -45: "-45°", 90: "90°"}


def normalize_ply_counts_for_symmetry(ply_counts: Dict[int, int]) -> Dict[str, Any]:
    """
    Ply sayılarını simetri üretilebilir hale getirir.

    Kural:
    - Toplam çift ise tüm açı adetleri çift olmalı.
    - Toplam tek ise yalnızca bir açı tek olabilir (orta ply).

    Multi-zone girişlerinde kullanıcı 7/7 gibi tek değerler verdiğinde
    otomatik olarak aşağı yuvarlamak için kullanılır.
    """
    counts = {}
    for angle in ANGLE_ORDER:
        counts[angle] = max(0, int(ply_counts.get(angle, 0) or 0))

    total_before = sum(counts.values())
    odd_angles = [angle for angle in ANGLE_ORDER if counts[angle] % 2 == 1]
    adjustments = []

    if total_before % 2 == 0:
        for angle in odd_angles:
            old_value = counts[angle]
            if old_value <= 0:
                continue
            counts[angle] = old_value - 1
            adjustments.append(
                {
                    "angle": angle,
                    "label": ANGLE_LABELS[angle],
                    "old_value": old_value,
                    "new_value": counts[angle],
                    "reason": "even_total_requires_even_counts",
                }
            )
    elif len(odd_angles) > 1:
        keep_angle = max(
            odd_angles,
            key=lambda angle: (counts[angle], -ANGLE_ORDER.index(angle))
        )
        for angle in odd_angles:
            if angle == keep_angle:
                continue
            old_value = counts[angle]
            if old_value <= 0:
                continue
            counts[angle] = old_value - 1
            adjustments.append(
                {
                    "angle": angle,
                    "label": ANGLE_LABELS[angle],
                    "old_value": old_value,
                    "new_value": counts[angle],
                    "reason": "odd_total_allows_only_one_odd_angle",
                    "kept_middle_angle": keep_angle,
                }
            )

    return {
        "adjusted_counts": counts,
        "was_adjusted": len(adjustments) > 0,
        "adjustments": adjustments,
        "total_before": total_before,
        "total_after": sum(counts.values()),
    }


def check_symmetry_compatibility(ply_counts: Dict[int, int]) -> Dict[str, Any]:
    """
    Simetri uyumluluğunu kontrol eder.

    Returns:
        {
            'requires_user_choice': bool,
            'issues': list,
            'suggestions': list
        }
    """
    total = sum(ply_counts.values())
    is_odd_total = total % 2 == 1

    odd_angles = [angle for angle, count in ply_counts.items() if count % 2 == 1]

    issues = []
    suggestions = []

    # Durum 1: Tek sayılı toplam + 2+ tek sayılı açı
    if is_odd_total and len(odd_angles) > 1:
        issues.append(
            {
                "type": "multiple_odd_angles",
                "angles": odd_angles,
                "total": total,
                "message": "{} açı tek sayıda ({}°). Sadece biri ortaya gidebilir.".format(
                    len(odd_angles), ", ".join(map(str, odd_angles))
                ),
            }
        )

        for angle in odd_angles:
            adjusted = ply_counts.copy()
            adjusted[angle] = adjusted[angle] - 1
            suggestions.append(
                {
                    "type": "set_middle",
                    "middle_angle": angle,
                    "adjusted_counts": adjusted,
                    "description": "{}° ortaya koy, diğer tek sayılı açıları çift yap".format(angle),
                }
            )

    # Durum 2: Çift sayılı toplam + tek sayılı açılar
    if (not is_odd_total) and len(odd_angles) > 0:
        angle_45 = ply_counts.get(45, 0)
        angle_minus45 = ply_counts.get(-45, 0)

        if angle_45 % 2 == 1 and angle_minus45 % 2 == 1 and angle_45 == angle_minus45:
            issues.append(
                {
                    "type": "odd_45_balance",
                    "angles": [45, -45],
                    "total": total,
                    "message": "45° ve -45° her ikisi de tek sayıda ({}). Eşit sayıda kalmalı (Rule 2: Balance).".format(
                        angle_45
                    ),
                }
            )

            # Öneri 1: İkisini de +1 yap (toplam sabit kalsın diye 0 veya 90'dan düş)
            adjusted1 = ply_counts.copy()
            adjusted1[45] = angle_45 + 1
            adjusted1[-45] = angle_minus45 + 1
            total_adjustment = 2
            for adj_angle in [0, 90]:
                if adj_angle in adjusted1 and adjusted1[adj_angle] >= total_adjustment:
                    adjusted1[adj_angle] -= total_adjustment
                    suggestions.append(
                        {
                            "type": "increase_45_pair",
                            "compensation_angle": adj_angle,
                            "compensation_amount": total_adjustment,
                            "adjusted_counts": adjusted1,
                            "description": "45° ve -45° → {} (her ikisi +1), {}° → {} (... - {})".format(
                                angle_45 + 1, adj_angle, adjusted1[adj_angle], total_adjustment
                            ),
                        }
                    )
                    break

            # Öneri 2: İkisini de -1 yap (toplam sabit kalsın diye 0 veya 90'a ekle)
            adjusted2 = ply_counts.copy()
            adjusted2[45] = angle_45 - 1
            adjusted2[-45] = angle_minus45 - 1
            total_adjustment = 2
            for adj_angle in [0, 90]:
                if adj_angle in adjusted2:
                    adjusted2[adj_angle] += total_adjustment
                    suggestions.append(
                        {
                            "type": "decrease_45_pair",
                            "compensation_angle": adj_angle,
                            "compensation_amount": total_adjustment,
                            "adjusted_counts": adjusted2,
                            "description": "45° ve -45° → {} (her ikisi -1), {}° → {} (... + {})".format(
                                angle_45 - 1, adj_angle, adjusted2[adj_angle], total_adjustment
                            ),
                        }
                    )
                    break
        else:
            issues.append(
                {
                    "type": "odd_angles_even_total",
                    "angles": odd_angles,
                    "total": total,
                    "message": "Çift sayılı toplamda {} açı tek sayıda. Simetri için her açı çift sayıda olmalı.".format(
                        len(odd_angles)
                    ),
                }
            )

            for angle in odd_angles:
                adjusted = ply_counts.copy()
                adjusted[angle] = adjusted[angle] + 1
                suggestions.append(
                    {
                        "type": "make_even",
                        "angle": angle,
                        "adjusted_counts": adjusted,
                        "description": "{}°: {} → {} (çift sayı yap)".format(angle, ply_counts[angle], adjusted[angle]),
                    }
                )

    return {"requires_user_choice": len(issues) > 0, "issues": issues, "suggestions": suggestions}

