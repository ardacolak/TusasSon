"""
ML Surrogate Model egitim modulu.

scikit-learn MLPRegressor kullanarak fitness fonksiyonunu
taklit eden bir model egitir.
"""

import os
import time
import numpy as np
import joblib
from typing import Dict, Optional, Tuple

from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score

from .data_generator import generate_training_data, encode_sequence, encode_ply_counts, MAX_PLY_COUNT


# Varsayilan model ve veri yollari
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_PATH = os.path.join(_MODULE_DIR, "surrogate_model.pkl")
DEFAULT_DATA_PATH = os.path.join(_MODULE_DIR, "training_data.npz")


def train_surrogate(
    n_samples: int = 50000,
    model_path: Optional[str] = None,
    data_path: Optional[str] = None,
) -> Dict:
    """Surrogate model egit ve kaydet.

    Args:
        n_samples: Egitim icin uretilecek ornek sayisi
        model_path: Model dosya yolu (.pkl)
        data_path: Egitim verisi dosya yolu (.npz)

    Returns:
        Egitim metrikleri: {mae, r2, train_time, n_samples, model_path}
    """
    if model_path is None:
        model_path = DEFAULT_MODEL_PATH
    if data_path is None:
        data_path = DEFAULT_DATA_PATH

    print(f"Veri uretiliyor ({n_samples} ornek)...")
    start = time.time()

    # Veri uret veya mevcut veriyi yukle
    if os.path.exists(data_path):
        print(f"Mevcut veri yukleniyor: {data_path}")
        data = np.load(data_path)
        X, y = data["X"], data["y"]
        if len(X) < n_samples:
            print(f"Mevcut veri yetersiz ({len(X)} < {n_samples}), yeni veri uretiliyor...")
            X, y = generate_training_data(n_samples=n_samples, save_path=data_path)
    else:
        X, y = generate_training_data(n_samples=n_samples, save_path=data_path)

    data_time = time.time() - start
    print(f"Veri hazir: {len(X)} ornek, {data_time:.1f}s")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42
    )

    # Pipeline: Scaler + MLP
    print("Model egitiliyor...")
    train_start = time.time()

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPRegressor(
            hidden_layer_sizes=(256, 128, 64),
            activation="relu",
            solver="adam",
            max_iter=200,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=15,
            learning_rate="adaptive",
            learning_rate_init=0.001,
            batch_size=256,
            random_state=42,
            verbose=False,
        )),
    ])

    pipeline.fit(X_train, y_train)
    train_time = time.time() - train_start

    # Degerlendirme
    y_pred = pipeline.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    print(f"Egitim tamamlandi: {train_time:.1f}s")
    print(f"  MAE: {mae:.3f} (hedef < 2.0)")
    print(f"  R2:  {r2:.4f}")

    # Model kaydet
    joblib.dump(pipeline, model_path)
    print(f"Model kaydedildi: {model_path}")

    return {
        "mae": round(float(mae), 3),
        "r2": round(float(r2), 4),
        "train_time": round(train_time, 1),
        "data_time": round(data_time, 1),
        "n_samples": len(X),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "model_path": model_path,
    }


def load_surrogate(model_path: Optional[str] = None) -> Optional[Pipeline]:
    """Kaydedilmis surrogate modeli yukle.

    Returns:
        Pipeline nesnesi veya model yoksa None
    """
    if model_path is None:
        model_path = DEFAULT_MODEL_PATH

    if not os.path.exists(model_path):
        return None

    return joblib.load(model_path)


def predict_fitness(
    model: Pipeline,
    sequence: list,
    ply_counts: Dict[int, int],
) -> float:
    """Surrogate model ile fitness tahmini yap.

    Args:
        model: Egitilmis pipeline
        sequence: Ply acilari listesi
        ply_counts: Ply sayilari dict'i

    Returns:
        Tahmini fitness skoru (0-100)
    """
    seq_encoded = encode_sequence(sequence)
    counts_encoded = encode_ply_counts(ply_counts)
    total_ply = np.array([len(sequence) / MAX_PLY_COUNT], dtype=np.float32)

    features = np.concatenate([seq_encoded, counts_encoded, total_ply])
    features = features.reshape(1, -1)

    prediction = float(model.predict(features)[0])
    return max(0.0, min(100.0, prediction))


def get_model_status(model_path: Optional[str] = None) -> Dict:
    """Model durumunu sorgula.

    Returns:
        {exists, model_path, file_size_mb}
    """
    if model_path is None:
        model_path = DEFAULT_MODEL_PATH

    exists = os.path.exists(model_path)
    file_size = 0
    if exists:
        file_size = os.path.getsize(model_path) / (1024 * 1024)

    return {
        "exists": exists,
        "model_path": model_path,
        "file_size_mb": round(file_size, 2),
    }
