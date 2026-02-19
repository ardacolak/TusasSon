"""
ML Surrogate Model icin egitim verisi uretici.

Mevcut LaminateOptimizer.calculate_fitness() fonksiyonunu kullanarak
rastgele sequence'ler uretir ve fitness skorlarini hesaplar.
"""

import random
import os
import numpy as np
from typing import Dict, List, Tuple, Optional

from ..core.laminate_optimizer import LaminateOptimizer


# One-hot encoding mapping: 0°, 90°, +45°, -45°
ANGLE_TO_ONEHOT = {
    0: [1, 0, 0, 0],
    90: [0, 1, 0, 0],
    45: [0, 0, 1, 0],
    -45: [0, 0, 0, 1],
}

# Desteklenen max ply sayisi (padding icin)
MAX_PLY_COUNT = 120


def encode_sequence(sequence: List[int], max_len: int = MAX_PLY_COUNT) -> np.ndarray:
    """Sequence'i one-hot encoded sabit uzunlukta vektore donustur.

    Args:
        sequence: Ply acilari listesi (ornegin [45, -45, 0, 90, ...])
        max_len: Padding icin max uzunluk

    Returns:
        (max_len * 4,) boyutunda numpy array
    """
    encoded = np.zeros(max_len * 4, dtype=np.float32)
    for i, angle in enumerate(sequence):
        if i >= max_len:
            break
        offset = i * 4
        onehot = ANGLE_TO_ONEHOT.get(angle, [0, 0, 0, 0])
        encoded[offset:offset + 4] = onehot
    return encoded


def encode_ply_counts(ply_counts: Dict[int, int]) -> np.ndarray:
    """Ply sayilarini normalize ederek sabit uzunlukta vektore donustur.

    Args:
        ply_counts: {0: n0, 90: n90, 45: n45, -45: n_45}

    Returns:
        (4,) boyutunda numpy array (normalize edilmis)
    """
    total = max(1, sum(ply_counts.values()))
    return np.array([
        ply_counts.get(0, 0) / total,
        ply_counts.get(90, 0) / total,
        ply_counts.get(45, 0) / total,
        ply_counts.get(-45, 0) / total,
    ], dtype=np.float32)


def generate_random_sequence(ply_counts: Dict[int, int]) -> List[int]:
    """Verilen ply sayilarina uygun rastgele sequence uret."""
    pool = []
    for angle, count in ply_counts.items():
        pool.extend([angle] * int(count))
    random.shuffle(pool)
    return pool


def generate_training_data(
    n_samples: int = 50000,
    ply_configs: Optional[List[Dict[int, int]]] = None,
    save_path: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Egitim verisi uret.

    Args:
        n_samples: Uretilecek toplam ornek sayisi
        ply_configs: Kullanilacak ply konfigurasyonlari listesi.
                     None ise varsayilan konfigurasyonlar kullanilir.
        save_path: Verinin kaydedilecegi dosya yolu (.npz)

    Returns:
        (X, y) tuple: X = feature matrix, y = fitness scores
    """
    if ply_configs is None:
        ply_configs = _default_ply_configs()

    X_list = []
    y_list = []

    samples_per_config = max(1, n_samples // len(ply_configs))

    for config in ply_configs:
        optimizer = LaminateOptimizer(config)

        for _ in range(samples_per_config):
            seq = generate_random_sequence(config)
            fitness, _ = optimizer.calculate_fitness(seq)
            fitness = float(fitness)

            seq_encoded = encode_sequence(seq)
            counts_encoded = encode_ply_counts(config)
            total_ply = np.array([len(seq) / MAX_PLY_COUNT], dtype=np.float32)

            features = np.concatenate([seq_encoded, counts_encoded, total_ply])
            X_list.append(features)
            y_list.append(fitness)

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)

    # Karistir
    indices = np.arange(len(X))
    np.random.shuffle(indices)
    X = X[indices]
    y = y[indices]

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        np.savez_compressed(save_path, X=X, y=y)
        print(f"Egitim verisi kaydedildi: {save_path} ({len(X)} ornek)")

    return X, y


def _default_ply_configs() -> List[Dict[int, int]]:
    """Varsayilan ply konfigurasyonlari.

    Farkli ply sayilari ve oranlariyla cesitlilik saglar.
    """
    configs = []

    # Standart dengeli konfigurasyonlar
    for n in [4, 6, 8, 10, 12, 14, 16, 18, 20]:
        configs.append({0: n, 90: n, 45: n, -45: n})

    # Asimetrik konfigurasyonlar
    for n_base in [6, 10, 14, 18]:
        configs.append({0: n_base + 4, 90: n_base, 45: n_base + 2, -45: n_base + 2})
        configs.append({0: n_base, 90: n_base + 4, 45: n_base + 2, -45: n_base + 2})
        configs.append({0: n_base + 2, 90: n_base + 2, 45: n_base + 4, -45: n_base})

    # Kucuk konfigurasyonlar
    configs.append({0: 4, 90: 4, 45: 4, -45: 4})
    configs.append({0: 2, 90: 2, 45: 4, -45: 4})

    return configs
