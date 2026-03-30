import random
from typing import Dict, List, Tuple, Optional

import numpy as np

from .laminate_optimizer import LaminateOptimizer


class DropOffOptimizer:
    """
    Tapering optimizer for ply drop-off.
    """

    MAX_CONSECUTIVE_DROPS = 2
    DEFAULT_HARD_RULES = {
        "max_two_consecutive_drops": True,
        "adjacent_0_90": True,
    }

    def __init__(self, master_sequence: List[int], base_optimizer: LaminateOptimizer, hard_rules: Optional[Dict[str, bool]] = None):
        self.master_sequence = master_sequence
        self.base_opt = base_optimizer
        self.total_plies = len(master_sequence)
        self.hard_rules = dict(self.DEFAULT_HARD_RULES)
        inherited = getattr(base_optimizer, "hard_rules", {}) or {}
        for key, value in inherited.items():
            if key in self.hard_rules:
                self.hard_rules[key] = bool(value)
        if hard_rules:
            for key, value in hard_rules.items():
                if key in self.hard_rules:
                    self.hard_rules[key] = bool(value)

    def _hard_rule_enabled(self, key: str) -> bool:
        return bool(self.hard_rules.get(key, self.DEFAULT_HARD_RULES.get(key, True)))

    @staticmethod
    def _flatten_dropped_by_angle(dropped_by_angle: Dict[int, List[int]]) -> List[int]:
        flat = []
        for indices in (dropped_by_angle or {}).values():
            flat.extend(int(idx) for idx in indices)
        return flat

    def _has_excessive_drop_run(self, drop_indices: List[int]) -> bool:
        if not self._hard_rule_enabled("max_two_consecutive_drops"):
            return False
        sorted_unique = sorted({
            int(idx) for idx in (drop_indices or [])
            if idx is not None
        })
        if not sorted_unique:
            return False

        run_len = 1
        for i in range(1, len(sorted_unique)):
            if sorted_unique[i] == sorted_unique[i - 1] + 1:
                run_len += 1
                if run_len > self.MAX_CONSECUTIVE_DROPS:
                    return True
            else:
                run_len = 1
        return False

    @staticmethod
    def _is_forbidden_adjacent(a: int, b: int) -> bool:
        return (a == 0 and b == 90) or (a == 90 and b == 0)

    def _normalize_sequence_after_drop(
        self,
        seq: List[int],
        pos_map: Optional[List[int]] = None,
    ) -> Tuple[List[int], Optional[List[int]]]:
        """
        Preserve the exact surviving ply order after drop-off.

        If removing plies creates a forbidden 0/90 adjacency, that candidate must
        be rejected by the caller instead of silently reordering the remaining
        laminate.
        """
        normalized_seq = list(seq)
        normalized_pos = list(pos_map) if pos_map is not None else None

        return normalized_seq, normalized_pos

    def optimize_drop(self, target_ply: int) -> Tuple[List[int], float, List[int]]:
        """
        Drop-off optimization with odd/even ply support.

        Supports:
        - Even → Even: Normal symmetric drop (pairs)
        - Odd → Odd: Symmetric drop (pairs), middle ply preserved
        - Odd → Even: Drop middle ply + symmetric pairs
        - Even → Odd: Break one pair - keep one as middle, drop its mirror
        """
        remove_cnt = self.total_plies - target_ply
        if remove_cnt <= 0:
            return self.master_sequence, 0.0, []

        master_is_odd = self.total_plies % 2 == 1
        target_is_odd = target_ply % 2 == 1
        half_len = self.total_plies // 2
        middle_idx = half_len if master_is_odd else None  # Ortadaki ply'ın index'i

        # Drop stratejisini belirle
        drop_middle = False
        break_pair_for_middle = False  # Çift → Tek için: bir çifti kır
        break_pair_idx = None  # Kırılacak çiftin sol yarıdaki pozisyonu

        if master_is_odd and not target_is_odd:
            # Tek → Çift: Ortadaki ply'ı da drop et
            drop_middle = True
            pairs_to_remove = (remove_cnt - 1) // 2
        elif not master_is_odd and target_is_odd:
            # Çift → Tek: Bir çifti kır - soldaki ortaya geçer, sağdaki drop edilir
            break_pair_for_middle = True
            # remove_cnt tek olmalı (örn: 36→35 = 1, 36→33 = 3)
            # Bir ply ortaya geçecek, geri kalan çiftler halinde drop edilecek
            pairs_to_remove = (remove_cnt - 1) // 2  # Örn: 1→0, 3→1, 5→2
        else:
            # Tek → Tek veya Çift → Çift: Normal çift drop
            if remove_cnt % 2 != 0:
                remove_cnt += 1  # Çift sayıya yuvarla
            pairs_to_remove = remove_cnt // 2

        # External plies koruması: ilk 2 katmanı koru (pozisyon 0 ve 1)
        # Rule 4'e göre ilk 2 ve son 2 katman korunmalı
        search_indices = list(range(2, half_len))  # Pozisyon 0 ve 1 hariç

        best_candidate = None
        best_key = None
        best_dropped = []

        attempts = self.base_opt.DROP_OFF_ATTEMPTS
        for _ in range(attempts):
            left_drops = []

            # Çift → Tek: Bir çifti kırmak için pozisyon seç
            if break_pair_for_middle:
                if len(search_indices) == 0:
                    continue
                # Ortaya yakın bir pozisyon seç (sol yarının sonlarından)
                # Bu pozisyondaki ply ortaya geçecek, mirror'ı drop edilecek
                break_pair_idx = random.choice(search_indices)

            # Normal çift drop pozisyonları seç
            if pairs_to_remove > 0 and len(search_indices) > 0:
                # break_pair_idx zaten kullanıldıysa onu hariç tut
                available_indices = [i for i in search_indices if i != break_pair_idx]
                sample_size = min(pairs_to_remove, len(available_indices))
                if sample_size > 0:
                    left_drops = random.sample(available_indices, sample_size)
                    left_drops.sort()

            # ✅ 1. NO GROUPING CHECK - Ardışık drop pozisyonları yasak
            # Drop pozisyonları birbirine çok yakın olmamalı (gruplama önleme)
            if len(left_drops) > 1:
                has_consecutive = any(left_drops[i + 1] - left_drops[i] == 1 for i in range(len(left_drops) - 1))
                if has_consecutive:
                    continue  # Grouped drops = reddet

            # ✅ 2. UNIFORM DISTRIBUTION CHECK - Drop'lar düzgün dağıtılmış olmalı
            spacing_std = 0.0  # Default değer
            if len(left_drops) > 2:
                spacings = [left_drops[i + 1] - left_drops[i] for i in range(len(left_drops) - 1)]
                spacing_mean = np.mean(spacings)
                spacing_std = np.std(spacings)
                # Çok yüksek standart sapma = kötü dağılım (AVOID örneği gibi)
                if spacing_std > spacing_mean * 0.7:  # Çok düzensiz dağılım
                    continue

            all_drops = []
            for idx in left_drops:
                all_drops.append(idx)
                all_drops.append(self.total_plies - 1 - idx)

            # Ortadaki ply'ı drop et (eğer gerekiyorsa - Tek → Çift)
            if drop_middle and middle_idx is not None:
                all_drops.append(middle_idx)

            # Çift → Tek: Bir çifti kır - sadece sağ yarıdaki mirror'ı drop et
            # Sol yarıdaki ply otomatik olarak yeni ortada kalır
            if break_pair_for_middle and break_pair_idx is not None:
                mirror_idx = self.total_plies - 1 - break_pair_idx
                all_drops.append(mirror_idx)

            all_drops.sort()
            if self._has_excessive_drop_run(all_drops):
                continue

            temp_seq = [ang for i, ang in enumerate(self.master_sequence) if i not in all_drops]
            temp_seq, _ = self._normalize_sequence_after_drop(temp_seq)

            # ✅ 3. MULTI-ANGLE CHECK - Sadece bir açıdan drop olmasın (0° dahil tüm açılar)
            dropped_angles_left = [self.master_sequence[idx] for idx in left_drops]
            if drop_middle and middle_idx is not None:
                dropped_angles_left.append(self.master_sequence[middle_idx])
            if break_pair_for_middle and break_pair_idx is not None:
                # Kırılan çiftin mirror'ını da ekle (sağ yarıdaki drop edilen)
                mirror_idx = self.total_plies - 1 - break_pair_idx
                dropped_angles_left.append(self.master_sequence[mirror_idx])
            unique_angles_dropped = set(dropped_angles_left)

            # Eğer sadece bir açıdan drop varsa ve toplam drop sayısı 2'den fazlaysa, reddet
            # Bu, 0°, 90°, 45°, -45° tüm açılar için geçerli
            # Özellikle 0°'dan da drop yapılabilmeli, ama tek başına olmamalı
            if len(unique_angles_dropped) == 1 and len(dropped_angles_left) > 2:
                continue  # Sadece bir açıdan drop yapılmış = reddet

            # ✅ 4. BALANCE CHECK (45°/-45° alternasyon + tüm açılar için denge)
            # Drop edilen açıların dağılımı dengeli olmalı
            count_45 = dropped_angles_left.count(45)
            count_minus45 = dropped_angles_left.count(-45)
            count_0 = dropped_angles_left.count(0)
            count_90 = dropped_angles_left.count(90)

            # 90°'dan aşırı drop yapılmasını engelle (en fazla 3 çift = 6 ply)
            if count_90 > 3:
                continue

            # 45°/-45° düşüşünü teşvik et: 4+ drop varsa en az bir 45° veya -45° olmalı
            total_drops = len(dropped_angles_left)
            if total_drops >= 4 and count_45 == 0 and count_minus45 == 0:
                continue

            # 45°/-45° dengesi kontrolü
            if count_45 > 0 or count_minus45 > 0:
                # Eğer her ikisi de varsa, sayıları yakın olmalı
                if count_45 > 0 and count_minus45 > 0:
                    if abs(count_45 - count_minus45) > 2:  # Çok dengesiz
                        continue
                # Eğer sadece biri varsa ve sayı 2'den fazlaysa, bu da dengesizlik
                elif (count_45 > 2 and count_minus45 == 0) or (count_minus45 > 2 and count_45 == 0):
                    continue

            total_score, details = self.base_opt.calculate_fitness(temp_seq)

            # 🚫 HARD FAIL (Hard constraints ihlali)
            if total_score <= 0:
                continue

            rules = details["rules"]

            # ✅ 5. RULE 6 (GROUPING) ÖZEL KONTROL - Drop sonrası grouping kontrolü
            # 3'lü veya daha fazla grouping varsa reddet
            groups_of_3 = self.base_opt._find_groups_of_size(temp_seq, 3)
            groups_of_4 = self.base_opt._find_groups_of_size(temp_seq, 4)
            groups_of_5 = self.base_opt._find_groups_of_size(temp_seq, 5)
            groups_of_4_or_more = groups_of_4 + groups_of_5  # 4 veya daha fazla

            # 4 veya daha fazla grouping varsa kesinlikle reddet
            if groups_of_4_or_more > 0:
                continue

            # 3'lü grouping sayısı fazla ise (3'ten fazla) reddet
            if groups_of_3 > 3:
                continue

            # ✅ 6. TÜM KURALLAR (R1-R8) MİNİMUM SKOR KONTROLÜ
            # Drop-off yapınca kuralların dışına çıkmamalı - minimum skorları koru
            min_scores = {
                "R1": 0.85,  # Symmetry - %85 minimum
                "R2": 0.80,  # Balance - %80 minimum
                "R3": 0.80,  # Percentage - %80 minimum
                "R4": 0.75,  # External plies - %75 minimum
                "R5": 0.70,  # Distribution - %70 minimum
                "R6": 0.75,  # Grouping - %75 minimum (önemli!)
                "R7": 0.75,  # Buckling - %75 minimum
                "R8": 0.85,  # Lateral bending - %85 minimum
            }

            # Her kural için minimum skor kontrolü
            rule_violations = 0
            for rule_name, min_ratio in min_scores.items():
                if rule_name in rules:
                    rule_weight = rules[rule_name]["weight"]
                    rule_score = rules[rule_name]["score"]
                    rule_ratio = rule_score / rule_weight if rule_weight > 0 else 0

                    if rule_ratio < min_ratio:
                        rule_violations += 1

            # Çok fazla kural ihlali varsa reddet (2'den fazla kural %75'in altındaysa)
            if rule_violations > 2:
                continue

            # ✅ 7. IMPROVED SELECTION KEY (lexicographic) - Tüm kuralları dikkate al
            # Uniform distribution score (düşük std = iyi)
            dist_score = spacing_std  # Zaten yukarıda hesaplandı

            # Angle diversity score (daha fazla farklı açı = iyi)
            angle_diversity = len(unique_angles_dropped)

            # Balance score (45°/-45° dengesi)
            balance_score = abs(count_45 - count_minus45) if (count_45 > 0 or count_minus45 > 0) else 0

            # Rule 6 (Grouping) penalty - düşük olmalı
            r6_penalty = rules.get("R6", {}).get("penalty", 0)

            # Tüm kuralların toplam penalty'si (düşük = iyi)
            total_penalty = sum(r.get("penalty", 0) for r in rules.values())

            # 0° drop bonusu - 0°'dan da drop yapıldıysa bonus ver (daha çeşitli drop için)
            # Ancak tek başına 0° olmamalı (zaten yukarıda kontrol edildi)
            has_0_drop = 1 if count_0 > 0 else 0

            # 90° drop penalty: çok sayıda 90° drop'u ittir
            ninety_drop_penalty = count_90 * 0.5

            # 45°/-45° drop bonusu: bu açılardan drop varsa ödüllendir
            has_45_drop_bonus = -1 if (count_45 > 0 or count_minus45 > 0) else 0

            key = (
                rule_violations,  # Primary: Kural ihlali sayısı (düşük = iyi, 0 = hiç ihlal yok)
                groups_of_3,  # Secondary: 3'lü grup sayısı (düşük = iyi)
                groups_of_4_or_more,  # Tertiary: 4+ grup sayısı (düşük = iyi, 0 olmalı)
                r6_penalty,  # Quaternary: Rule 6 grouping penalty (düşük = iyi)
                ninety_drop_penalty,  # 90° drop penalty (düşük = iyi)
                rules["R1"]["penalty"] + rules["R8"]["penalty"],  # Quinary: R1 + R8 penalty
                dist_score,  # Senary: Uniform distribution (düşük = iyi)
                balance_score,  # Senaryedi: Balance (düşük = iyi)
                -angle_diversity,  # Sekizinci: Angle diversity (yüksek = iyi, negatif çünkü min istiyoruz)
                has_45_drop_bonus,  # 45°/-45° drop bonusu (negatif = ödül)
                -has_0_drop,  # Dokuzuncu: 0° drop bonusu (0° varsa -1, yoksa 0, negatif çünkü min istiyoruz)
                total_penalty,  # Onuncu: Toplam penalty
                -total_score,  # On birinci: Total fitness score (yüksek = iyi)
            )

            if best_key is None or key < best_key:
                best_key = key
                best_candidate = temp_seq
                best_dropped = all_drops

        if best_candidate is None:
            return self.master_sequence, 0.0, []

        return best_candidate, best_key[10] * -1, best_dropped  # Total score'u döndür (11. eleman)

    def optimize_drop_with_angle_targets(
        self, target_ply_counts: Dict[int, int]
    ) -> Tuple[List[int], float, Dict[int, List[int]]]:
        """
        Master sequence'den spesifik açı sayılarına göre drop yapar.
        """
        from collections import Counter

        def _greedy_angle_target_drop(
            seq_in: List[int],
            target_counts_in: Dict[int, int],
            protect_left_min_idx: int,
        ) -> Optional[Tuple[List[int], float, Dict[int, List[int]]]]:
            """
            Deterministic fallback when random sampling can't find a feasible set.

            We remove symmetric pairs (left idx + its mirror) one pair at a time,
            choosing the best-scoring (hard-constraints-safe) removal each step.
            For angles needing odd drops, single ply removal is done after pair drops.

            Returns:
              (new_seq, score, dropped_by_angle_in_original_parent_index_space) or None
            """
            seq = seq_in[:]
            pos_map = list(range(len(seq_in)))  # current position -> original index in parent sequence
            dropped_by_angle: Dict[int, List[int]] = {}

            # Feasibility check + separate even/odd deltas
            current = Counter(seq)
            greedy_pair_targets = {}  # Çift drop hedefleri (simetrik çift drop ile ulaşılacak)
            greedy_single_angles = []  # Tek kalan 1 ply drop gereken açılar

            for ang, tgt in target_counts_in.items():
                if tgt > current.get(ang, 0):
                    return None
                delta = current.get(ang, 0) - tgt
                if delta % 2 != 0:
                    # Tek delta: çift kısmı pair drop, kalan 1'i single drop
                    greedy_single_angles.append(int(ang))
                    greedy_pair_targets[int(ang)] = tgt + 1  # Çift hedefe pair drop
                else:
                    greedy_pair_targets[int(ang)] = tgt

            # Phase 1: Iteratively pair-drop until even targets satisfied
            safety_iter = 0
            while True:
                safety_iter += 1
                if safety_iter > 5000:
                    return None

                current = Counter(seq)
                # Pair drop phase done?
                done = True
                for ang, tgt in greedy_pair_targets.items():
                    if current.get(ang, 0) > tgt:
                        done = False
                        break
                if done:
                    break

                n = len(seq)
                half = n // 2
                best = None  # (score, ang, left_idx, drop_positions_set)

                for ang, tgt in greedy_pair_targets.items():
                    need = current.get(ang, 0) - tgt
                    if need < 2:
                        continue

                    # candidate left positions for this angle
                    for left_idx in range(half):
                        if left_idx < protect_left_min_idx:
                            continue
                        if seq[left_idx] != ang:
                            continue
                        right_idx = n - 1 - left_idx
                        if right_idx == left_idx:
                            continue
                        if seq[right_idx] != ang:
                            continue

                        candidate_drops = self._flatten_dropped_by_angle(dropped_by_angle) + [pos_map[left_idx], pos_map[right_idx]]
                        if self._has_excessive_drop_run(candidate_drops):
                            continue

                        drop_set = {left_idx, right_idx}
                        temp_seq = [a for i, a in enumerate(seq) if i not in drop_set]
                        temp_seq, _ = self._normalize_sequence_after_drop(temp_seq)
                        sc, _ = self.base_opt.calculate_fitness(temp_seq)
                        if sc <= 0:
                            continue

                        cand = (float(sc), ang, left_idx, drop_set)
                        if best is None or cand[0] > best[0]:
                            best = cand

                if best is None:
                    return None

                _sc, ang, left_idx, drop_set = best
                right_idx = max(drop_set)
                left_idx = min(drop_set)

                orig_left = pos_map[left_idx]
                orig_right = pos_map[right_idx]
                dropped_by_angle.setdefault(int(ang), []).extend([orig_left, orig_right])

                for idx in sorted(drop_set, reverse=True):
                    seq.pop(idx)
                    pos_map.pop(idx)
                seq, pos_map = self._normalize_sequence_after_drop(seq, pos_map)

            # Phase 2: Single ply drops for odd-delta angles (asimetrik, hafif simetri kaybı)
            if len(greedy_single_angles) >= 2:
                # Birden fazla single drop: birlikte kaldırmayı dene (0-90 separator sorunu)
                n = len(seq)
                angle_positions = {}
                for ang in greedy_single_angles:
                    angle_positions[ang] = [i for i in range(2, n - 2) if seq[i] == ang]

                # Tüm kombinasyonları dene, en iyi skoru bul
                from itertools import product
                pos_lists = [angle_positions[ang] for ang in greedy_single_angles]
                best_combo = None
                best_combo_score = -1.0

                for combo in product(*pos_lists):
                    if len(set(combo)) != len(combo):
                        continue  # Aynı pozisyon birden fazla açı için seçilmişse atla
                    combo_orig = [pos_map[pos] for pos in combo]
                    candidate_drops = self._flatten_dropped_by_angle(dropped_by_angle) + combo_orig
                    if self._has_excessive_drop_run(candidate_drops):
                        continue
                    drop_set = set(combo)
                    temp = [seq[k] for k in range(n) if k not in drop_set]
                    temp, _ = self._normalize_sequence_after_drop(temp)
                    sc, _ = self.base_opt.calculate_fitness(temp)
                    if sc > best_combo_score:
                        best_combo_score = sc
                        best_combo = combo

                if best_combo is None or best_combo_score <= 0:
                    return None

                # Birleşik kaldırma uygula
                for ang, pos in zip(greedy_single_angles, best_combo):
                    orig_idx = pos_map[pos]
                    dropped_by_angle.setdefault(int(ang), []).append(orig_idx)

                # Yüksek index'ten düşüğe doğru pop (index kayması önleme)
                for pos in sorted(best_combo, reverse=True):
                    seq.pop(pos)
                    pos_map.pop(pos)
                # 0°-90° bitişiklik düzelt
                seq, pos_map = self._normalize_sequence_after_drop(seq, pos_map)
            elif len(greedy_single_angles) == 1:
                # Tek single drop: sıralı kaldırma yeterli
                ang = greedy_single_angles[0]
                n = len(seq)
                best_pos = None
                best_score = -1.0
                for i in range(2, n - 2):
                    if seq[i] != ang:
                        continue
                    candidate_drops = self._flatten_dropped_by_angle(dropped_by_angle) + [pos_map[i]]
                    if self._has_excessive_drop_run(candidate_drops):
                        continue
                    temp = seq[:i] + seq[i + 1:]
                    temp, _ = self._normalize_sequence_after_drop(temp)
                    sc, _ = self.base_opt.calculate_fitness(temp)
                    if sc > best_score:
                        best_score = sc
                        best_pos = i
                if best_pos is None or best_score <= 0:
                    return None
                orig_idx = pos_map[best_pos]
                dropped_by_angle.setdefault(int(ang), []).append(orig_idx)
                seq.pop(best_pos)
                pos_map.pop(best_pos)
                seq, pos_map = self._normalize_sequence_after_drop(seq, pos_map)

            # Final validation
            score, _details = self.base_opt.calculate_fitness(seq)
            if score <= 0:
                return None
            return seq, float(score), {a: sorted(v) for a, v in dropped_by_angle.items()}

        def _beam_search_angle_target_drop(
            seq_in: List[int],
            target_counts_in: Dict[int, int],
            protect_left_min_idx: int,
            beam_width: int = 16,
        ) -> Optional[Tuple[List[int], float, Dict[int, List[int]]]]:
            """
            Stronger deterministic fallback than greedy.

            Beam-search over symmetric-pair drops to reach *exact* target counts while
            respecting hard constraints (fitness > 0).
            For angles needing odd drops, single ply removal is done after beam search.
            """
            if beam_width < 1:
                beam_width = 1

            seq0 = seq_in[:]
            pos0 = list(range(len(seq0)))  # current position -> original index (parent index space)
            current0 = Counter(seq0)

            # Determine required symmetric pair drops per angle + single drops for odd deltas
            pairs_needed = {}  # angle -> number of PAIRS to remove
            beam_single_angles = []  # angles needing 1 extra single drop

            for ang, tgt in target_counts_in.items():
                cur = current0.get(ang, 0)
                if tgt > cur:
                    return None
                delta = cur - tgt
                if delta % 2 != 0:
                    beam_single_angles.append(int(ang))
                    pair_delta = delta - 1  # Çift kısım
                else:
                    pair_delta = delta
                if pair_delta > 0:
                    pairs_needed[int(ang)] = pair_delta // 2

            total_pairs = sum(pairs_needed.values())
            if total_pairs == 0 and not beam_single_angles:
                sc, _ = self.base_opt.calculate_fitness(seq0)
                if sc <= 0:
                    return None
                return seq0, float(sc), {}

            # Phase 1: Beam search for symmetric pair drops
            sc0, _ = self.base_opt.calculate_fitness(seq0)
            if sc0 <= 0:
                return None

            if total_pairs > 0:
                beam = [(float(sc0), seq0, pos0, dict(pairs_needed), {})]

                for _step in range(total_pairs):
                    next_states = []

                    for _score, seq, pos_map, pairs_left, dropped in beam:
                        n = len(seq)
                        half = n // 2

                        for ang in sorted([a for a, k in pairs_left.items() if k > 0]):
                            for left_idx in range(max(protect_left_min_idx, 0), half):
                                if seq[left_idx] != ang:
                                    continue
                                right_idx = n - 1 - left_idx
                                if right_idx == left_idx:
                                    continue
                                if seq[right_idx] != ang:
                                    continue

                                temp_seq = seq[:]
                                temp_pos = pos_map[:]
                                orig_left = temp_pos[left_idx]
                                orig_right = temp_pos[right_idx]

                                candidate_drops = self._flatten_dropped_by_angle(dropped) + [orig_left, orig_right]
                                if self._has_excessive_drop_run(candidate_drops):
                                    continue

                                temp_seq.pop(right_idx)
                                temp_pos.pop(right_idx)
                                temp_seq.pop(left_idx)
                                temp_pos.pop(left_idx)
                                temp_seq, temp_pos = self._normalize_sequence_after_drop(temp_seq, temp_pos)

                                sc, _ = self.base_opt.calculate_fitness(temp_seq)
                                if sc <= 0:
                                    continue

                                new_pairs_left = dict(pairs_left)
                                new_pairs_left[ang] = new_pairs_left.get(ang, 0) - 1
                                if new_pairs_left[ang] <= 0:
                                    new_pairs_left.pop(ang, None)

                                new_dropped = {k: v[:] for k, v in dropped.items()}
                                new_dropped.setdefault(int(ang), []).extend([orig_left, orig_right])

                                next_states.append((float(sc), temp_seq, temp_pos, new_pairs_left, new_dropped))

                    if not next_states:
                        return None

                    next_states.sort(key=lambda x: x[0], reverse=True)
                    seen = set()
                    new_beam = []
                    for st in next_states:
                        key = tuple(st[1])
                        if key in seen:
                            continue
                        seen.add(key)
                        new_beam.append(st)
                        if len(new_beam) >= beam_width:
                            break
                    beam = new_beam

                best = max(beam, key=lambda x: x[0])
            else:
                # No pair drops needed, only single drops
                best = (float(sc0), seq0[:], pos0[:], {}, {})

            best_seq = best[1]
            best_pos_map = best[2]
            best_dropped = best[4] if len(best) > 4 else {}

            # Phase 2: Single ply drops for odd-delta angles
            if len(beam_single_angles) >= 2:
                # Birden fazla single drop: birlikte kaldır (separator sorunu)
                from itertools import product
                n = len(best_seq)
                angle_positions = {}
                for ang in beam_single_angles:
                    angle_positions[ang] = [i for i in range(2, n - 2) if best_seq[i] == ang]

                pos_lists = [angle_positions[ang] for ang in beam_single_angles]
                best_combo = None
                best_combo_score = -1.0

                for combo in product(*pos_lists):
                    if len(set(combo)) != len(combo):
                        continue
                    combo_orig = [best_pos_map[pos] for pos in combo]
                    candidate_drops = self._flatten_dropped_by_angle(best_dropped) + combo_orig
                    if self._has_excessive_drop_run(candidate_drops):
                        continue
                    drop_set = set(combo)
                    temp = [best_seq[k] for k in range(n) if k not in drop_set]
                    temp, _ = self._normalize_sequence_after_drop(temp)
                    sc, _ = self.base_opt.calculate_fitness(temp)
                    if sc > best_combo_score:
                        best_combo_score = sc
                        best_combo = combo

                if best_combo is None or best_combo_score <= 0:
                    return None

                best_dropped = {k: v[:] for k, v in best_dropped.items()}
                for ang, pos in zip(beam_single_angles, best_combo):
                    orig_idx = best_pos_map[pos]
                    best_dropped.setdefault(int(ang), []).append(orig_idx)

                for pos in sorted(best_combo, reverse=True):
                    best_seq.pop(pos)
                    best_pos_map.pop(pos)
                # 0°-90° bitişiklik düzelt
                best_seq, best_pos_map = self._normalize_sequence_after_drop(best_seq, best_pos_map)
            elif len(beam_single_angles) == 1:
                ang = beam_single_angles[0]
                n = len(best_seq)
                best_pos = None
                best_sc = -1.0
                for i in range(2, n - 2):
                    if best_seq[i] != ang:
                        continue
                    candidate_drops = self._flatten_dropped_by_angle(best_dropped) + [best_pos_map[i]]
                    if self._has_excessive_drop_run(candidate_drops):
                        continue
                    temp = best_seq[:i] + best_seq[i + 1:]
                    temp, _ = self._normalize_sequence_after_drop(temp)
                    sc, _ = self.base_opt.calculate_fitness(temp)
                    if sc > best_sc:
                        best_sc = sc
                        best_pos = i
                if best_pos is None or best_sc <= 0:
                    return None
                orig_idx = best_pos_map[best_pos]
                best_dropped = {k: v[:] for k, v in best_dropped.items()}
                best_dropped.setdefault(int(ang), []).append(orig_idx)
                best_seq.pop(best_pos)
                best_pos_map.pop(best_pos)
                best_seq, best_pos_map = self._normalize_sequence_after_drop(best_seq, best_pos_map)

            # Final validation
            final_score, _ = self.base_opt.calculate_fitness(best_seq)
            if final_score <= 0:
                return None
            return best_seq, float(final_score), {a: sorted(v) for a, v in best_dropped.items()}

        # 1. Validation: Target counts kontrolü
        current_counts = dict(Counter(self.master_sequence))

        for angle, target_count in target_ply_counts.items():
            current = current_counts.get(angle, 0)
            if target_count > current:
                raise ValueError(
                    "Angle {}°: hedef {} ama mevcut sadece {} katman var".format(angle, target_count, current)
                )
            if target_count < 0:
                raise ValueError("Angle {}°: hedef sayı negatif olamaz".format(angle))

        # 2. Her açıdan kaç ply düşeceğini hesapla
        drops_needed = {}
        for angle, target_count in target_ply_counts.items():
            current = current_counts.get(angle, 0)
            if current > target_count:
                drops_needed[angle] = current - target_count

        # Toplam düşürülecek ply sayısı
        total_drops = sum(drops_needed.values())

        if total_drops == 0:
            # Hiç drop gerekmiyorsa master sequence'i döndür
            score, _ = self.base_opt.calculate_fitness(self.master_sequence)
            return self.master_sequence[:], score, {}

        # 3. Her açı için drop edilebilir pozisyonları bul (sol yarıdan)
        n = len(self.master_sequence)
        half = n // 2
        master_is_odd = n % 2 == 1
        middle_idx = half if master_is_odd else None
        middle_angle = self.master_sequence[middle_idx] if middle_idx is not None else None

        # Tek/çift durumu kontrolü
        target_total = sum(target_ply_counts.values())
        target_is_odd = target_total % 2 == 1

        # Ortadaki ply drop edilecek mi? / Bir çift kırılacak mı?
        drop_middle = False
        break_pair_for_middle = False
        break_pair_angle = None  # Çift kırılacak açı

        if master_is_odd and not target_is_odd:
            # Tek → Çift: Ortadaki ply'ı drop et
            drop_middle = True
            if middle_angle in drops_needed:
                drops_needed[middle_angle] -= 1
                if drops_needed[middle_angle] == 0:
                    del drops_needed[middle_angle]
        elif not master_is_odd and target_is_odd:
            # Çift → Tek: Bir çifti kır - bir ply ortaya geçecek
            break_pair_for_middle = True
            # Tek sayıda drop gereken açıyı bul
            for angle, count in drops_needed.items():
                if count % 2 == 1:
                    break_pair_angle = angle
                    drops_needed[angle] -= 1  # Çift yap (bir tanesi ortaya geçecek)
                    if drops_needed[angle] == 0:
                        del drops_needed[angle]
                    break
            # Eğer hiçbiri tek değilse, herhangi birinden kır
            if break_pair_angle is None and drops_needed:
                break_pair_angle = list(drops_needed.keys())[0]

        # Her açının simetrik (çift) drop sayısını belirle
        # Tek kalan 1 ply asimetrik drop ile çözülecek (hafif simetri kaybı kabul edilir)
        single_ply_drops = {}  # angle -> 1 (asimetrik tek ply drop gerekiyor)

        for angle in list(drops_needed.keys()):
            if drops_needed[angle] % 2 != 0:
                # Tek sayıda drop varsa, ortadaki ply bu açıdansa onu kullan
                if master_is_odd and middle_angle == angle and not drop_middle:
                    drop_middle = True
                    drops_needed[angle] -= 1
                    if drops_needed[angle] == 0:
                        del drops_needed[angle]
                else:
                    # Tek kalan 1 ply'ı asimetrik drop ile çöz
                    single_ply_drops[angle] = 1
                    drops_needed[angle] -= 1  # Çift sayıya indir
                    if drops_needed[angle] == 0:
                        del drops_needed[angle]

        angle_positions_left = {}  # Her açının sol yarıdaki pozisyonları
        angle_grouped_left = {}   # Her açının gruplanmış (ikili+) pozisyonları
        all_angles_to_check = set(drops_needed.keys())
        if break_pair_angle:
            all_angles_to_check.add(break_pair_angle)

        for angle in all_angles_to_check:
            positions = [i for i in range(half) if self.master_sequence[i] == angle]
            # External plies koruması: ilk 2 katmanı koru (pozisyon 0 ve 1)
            positions = [p for p in positions if p > 1]
            angle_positions_left[angle] = positions

            # Gruplanmış pozisyonları bul (yan yana aynı açı olan pozisyonlar)
            # Bu pozisyonlardan drop yapılırsa grouping kırılır
            grouped = set()
            for p in positions:
                if p > 0 and self.master_sequence[p - 1] == angle:
                    grouped.add(p)
                if p < n - 1 and self.master_sequence[p + 1] == angle:
                    grouped.add(p)
            angle_grouped_left[angle] = [p for p in positions if p in grouped]

        # Asimetrik tek-ply drop'lar için tüm pozisyonlar (sol+sağ yarı)
        angle_positions_all = {}
        for angle in single_ply_drops:
            positions = [i for i in range(n) if self.master_sequence[i] == angle]
            # External plies koruması: ilk 2 ve son 2 katmanı koru
            positions = [p for p in positions if 1 < p < n - 2]
            angle_positions_all[angle] = positions

        # 4. En iyi drop kombinasyonunu bul
        best_candidate = None
        best_score = -1
        best_dropped_by_angle = {}

        attempts = self.base_opt.ANGLE_TARGET_DROP_ATTEMPTS
        for attempt_idx in range(attempts):
            # Her açı için drop pozisyonları seç (sol yarıdan)
            # %70 ihtimalle gruplanmış pozisyonları tercih et (grouping kırma stratejisi)
            left_drops_by_angle = {}
            valid = True
            prefer_grouped = random.random() < 0.70

            for angle, drop_count in drops_needed.items():
                pairs_needed = drop_count // 2  # Simetrik droplar
                available = angle_positions_left.get(angle, [])
                grouped = angle_grouped_left.get(angle, [])

                if len(available) < pairs_needed:
                    valid = False
                    break

                if prefer_grouped and grouped:
                    # Gruplanmış pozisyonlardan öncelikli seç
                    ungrouped = [p for p in available if p not in grouped]
                    if len(grouped) >= pairs_needed:
                        selected = random.sample(grouped, pairs_needed)
                    else:
                        # Gruplanmış yetmiyorsa, kalanı ungrouped'dan al
                        selected = list(grouped)
                        remaining = pairs_needed - len(selected)
                        if len(ungrouped) >= remaining:
                            selected += random.sample(ungrouped, remaining)
                        else:
                            selected += ungrouped
                    selected = selected[:pairs_needed]
                else:
                    selected = random.sample(available, pairs_needed)

                left_drops_by_angle[angle] = sorted(selected)

            if not valid:
                continue

            # Tüm drop pozisyonlarını birleştir
            all_left_drops = []
            for positions in left_drops_by_angle.values():
                all_left_drops.extend(positions)
            all_left_drops.sort()

            # Ardışık drop kontrolü
            if len(all_left_drops) > 1:
                has_consecutive = any(
                    all_left_drops[i + 1] - all_left_drops[i] == 1 for i in range(len(all_left_drops) - 1)
                )
                if has_consecutive:
                    continue

            # Simetrik pozisyonları ekle (sağ yarıdan)
            all_drops = []
            all_drop_angles = set(drops_needed.keys()) | set(single_ply_drops.keys())
            dropped_by_angle = {angle: [] for angle in all_drop_angles}

            for angle, left_positions in left_drops_by_angle.items():
                for idx in left_positions:
                    all_drops.append(idx)
                    mirror_idx = n - 1 - idx
                    all_drops.append(mirror_idx)
                    dropped_by_angle[angle].extend([idx, mirror_idx])

            # Ortadaki ply'ı drop et (eğer gerekiyorsa - Tek → Çift)
            if drop_middle and middle_idx is not None:
                all_drops.append(middle_idx)
                if middle_angle not in dropped_by_angle:
                    dropped_by_angle[middle_angle] = []
                dropped_by_angle[middle_angle].append(middle_idx)

            # Çift → Tek: Bir çifti kır - sadece mirror'ı drop et
            break_pair_idx = None
            if break_pair_for_middle and break_pair_angle is not None:
                available_for_break = angle_positions_left.get(break_pair_angle, [])
                # left_drops_by_angle'da kullanılmamış bir pozisyon seç
                used_positions = left_drops_by_angle.get(break_pair_angle, [])
                available_for_break = [p for p in available_for_break if p not in used_positions]

                if available_for_break:
                    break_pair_idx = random.choice(available_for_break)
                    mirror_idx = n - 1 - break_pair_idx
                    all_drops.append(mirror_idx)
                    if break_pair_angle not in dropped_by_angle:
                        dropped_by_angle[break_pair_angle] = []
                    dropped_by_angle[break_pair_angle].append(mirror_idx)

            # Asimetrik tek-ply drop'ları ekle (simetriyi hafifçe kırarak hedef açı sayısına ulaş)
            single_valid = True
            if single_ply_drops:
                drops_set = set(all_drops)
                for s_angle in single_ply_drops:
                    available_for_single = [p for p in angle_positions_all.get(s_angle, [])
                                            if p not in drops_set]
                    if not available_for_single:
                        single_valid = False
                        break
                    single_pos = random.choice(available_for_single)
                    all_drops.append(single_pos)
                    drops_set.add(single_pos)
                    dropped_by_angle[s_angle].append(single_pos)

            if not single_valid:
                continue

            all_drops.sort()
            if self._has_excessive_drop_run(all_drops):
                continue

            # Yeni sequence oluştur
            temp_seq = [ang for i, ang in enumerate(self.master_sequence) if i not in all_drops]

            # Single drop'lar 0°-90° bitişiklik yaratmışsa swap ile düzelt
            temp_seq, _ = self._normalize_sequence_after_drop(temp_seq)

            # Fitness hesapla
            score, details = self.base_opt.calculate_fitness(temp_seq)

            # Hard constraint ihlali varsa atla
            if score <= 0:
                continue

            # Hedef açı sayılarına ulaşıldı mı kontrol et (tam eşleşme)
            temp_counts = Counter(temp_seq)

            matches_target = True
            for angle, orig_target in target_ply_counts.items():
                actual_count = temp_counts.get(angle, 0)
                if abs(actual_count - orig_target) > 0:
                    matches_target = False
                    break

            if not matches_target:
                continue

            # Grouping kalite kontrolü: 4+ gruplar kesinlikle reddet
            groups_of_4 = self.base_opt._find_groups_of_size(temp_seq, 4)
            groups_of_5 = self.base_opt._find_groups_of_size(temp_seq, 5)
            if groups_of_4 + groups_of_5 > 0:
                continue

            groups_of_3 = self.base_opt._find_groups_of_size(temp_seq, 3)

            # Çok fazla 3'lü grup varsa reddet
            if groups_of_3 > 4:
                continue

            # En iyi skoru güncelle (grouping kalitesi + fitness birlikte)
            candidate_key = (groups_of_3, -score)  # Önce az 3'lü grup, sonra yüksek skor
            best_key_current = (999, 0) if best_score < 0 else (getattr(self, '_best_g3', 999), -best_score)

            if best_candidate is None or candidate_key < best_key_current:
                best_score = score
                self._best_g3 = groups_of_3
                best_candidate = temp_seq
                best_dropped_by_angle = {angle: sorted(positions) for angle, positions in dropped_by_angle.items()}

        if best_candidate is None:
            # Fallback: deterministic search (beam/greedy) to avoid "zone copying"
            # when random sampling can't find a feasible combination.
            full_targets = dict(Counter(self.master_sequence))
            for a, t in target_ply_counts.items():
                full_targets[int(a)] = int(t)

            # Prefer beam-search (more robust), then greedy (cheaper).
            fallback_res = None
            for protect in (2, 1, 0):
                fallback_res = _beam_search_angle_target_drop(
                    self.master_sequence,
                    full_targets,
                    protect_left_min_idx=protect,
                    beam_width=16,
                )
                if fallback_res is None:
                    fallback_res = _greedy_angle_target_drop(self.master_sequence, full_targets, protect_left_min_idx=protect)
                if fallback_res is not None:
                    break

            if fallback_res is not None:
                new_seq, best_score, dropped_by_angle = fallback_res
                return new_seq, best_score, dropped_by_angle

            raise ValueError("Hedef açı sayılarına uygun drop kombinasyonu bulunamadı")

        return best_candidate, best_score, best_dropped_by_angle

