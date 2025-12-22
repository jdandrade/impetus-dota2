#!/usr/bin/env python3
"""
Phase 18: Penta-Role Regression Analysis

Performs granular regression analysis on Stratz IMP data,
splitting by all 5 positions for maximum accuracy.

Features:
- 5-role buckets (Pos 1-5)
- Ridge Regression (Alpha=1.0)
- KDA and per-minute feature engineering
- Copy-paste ready coefficient output

Usage:
    python scripts/solve_formula.py

Reference - Stratz IMP Variables (27 metrics):
- Game Time, Kills, Deaths, Assists, Net Worth, Creep Score, Denies, Level
- Hero Damage, Tower Damage, Physical/Magical/Pure Damage, Damage Received
- Healing, Power Runes Controlled, Neutral Creep Kills, XP Fed, Actions/min
- Stun/Disable/Slow/Weaken Count & Duration
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from sklearn.metrics import r2_score, mean_absolute_error

# ============================================
# Configuration
# ============================================

INPUT_FILE = "data/stratz_big_data.csv"
RIDGE_ALPHA = 1.0

# Position names for output
POSITION_NAMES = {
    1: "POSITION_1",  # Safe Lane Carry
    2: "POSITION_2",  # Mid Lane
    3: "POSITION_3",  # Offlane
    4: "POSITION_4",  # Soft Support
    5: "POSITION_5",  # Hard Support
}

POSITION_DESCRIPTIONS = {
    1: "Safe Lane Carry",
    2: "Mid Lane",
    3: "Offlane",
    4: "Soft Support",
    5: "Hard Support",
}

# Features to use for regression (matching what we have in the dataset)
# Based on Stratz's 27 metrics and what we collected
BASE_FEATURES = [
    # Core stats
    "kills",
    "deaths",
    "assists",
    "gpm",
    "xpm",
    "networth",
    "level",
    "last_hits",
    "denies",
    
    # Damage stats
    "hero_damage",
    "tower_damage",
    "hero_healing",
    
    # Per-minute stats
    "kills_per_min",
    "deaths_per_min",
    "assists_per_min",
    "hero_damage_per_min",
    "tower_damage_per_min",
    "healing_per_min",
    
    # Win/loss context
    "is_victory",
    
    # Match duration (important context)
    "duration_minutes",
]

# Engineered features
ENGINEERED_FEATURES = [
    "kda_ratio",
    "ka_ratio",      # (K+A) / duration
    "death_rate",    # deaths / duration  
    "farm_efficiency",  # networth / duration
    "damage_efficiency",  # hero_damage / networth
]

# ============================================
# Data Loading
# ============================================

def load_data(filepath: str) -> list[dict]:
    """Load CSV data into list of dictionaries."""
    data = []
    try:
        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
    except FileNotFoundError:
        print(f"❌ Error: File not found: {filepath}")
        sys.exit(1)
    
    return data


def safe_float(value, default=0.0) -> float:
    """Safely convert to float."""
    try:
        if value is None or value == "" or value == "None":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0) -> int:
    """Safely convert to int."""
    try:
        if value is None or value == "" or value == "None":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def engineer_features(row: dict) -> dict:
    """Add engineered features to a row."""
    kills = safe_float(row.get("kills"))
    deaths = safe_float(row.get("deaths"))
    assists = safe_float(row.get("assists"))
    networth = safe_float(row.get("networth"))
    hero_damage = safe_float(row.get("hero_damage"))
    duration = safe_float(row.get("duration_minutes"), 1.0)
    
    row["kda_ratio"] = (kills + assists) / max(deaths, 1)
    row["ka_ratio"] = (kills + assists) / max(duration, 1)
    row["death_rate"] = deaths / max(duration, 1)
    row["farm_efficiency"] = networth / max(duration, 1)
    row["damage_efficiency"] = hero_damage / max(networth, 1) if networth > 0 else 0
    
    return row


def get_position(row: dict) -> int | None:
    """
    Determine player position (1-5).
    Handles formats like "POSITION_4", "4", or integer 4.
    """
    position_raw = row.get("position", "")
    
    # Handle POSITION_X format (e.g., "POSITION_4")
    if isinstance(position_raw, str) and position_raw.startswith("POSITION_"):
        try:
            pos = int(position_raw.replace("POSITION_", ""))
            if pos in [1, 2, 3, 4, 5]:
                return pos
        except ValueError:
            pass
    
    # Handle integer or numeric string
    position = safe_int(position_raw)
    if position in [1, 2, 3, 4, 5]:
        return position
    
    # Fallback: deduce from role_type (less accurate)
    role_type = row.get("role_type", "").lower()
    if role_type == "core":
        # Can't distinguish 1/2/3, return None to skip
        return None
    elif role_type == "support":
        # Can't distinguish 4/5, return None to skip
        return None
    
    return None


# ============================================
# Analysis Functions
# ============================================

def prepare_features(data: list[dict], feature_names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """
    Prepare feature matrix X and target vector y.
    """
    X = []
    y = []
    
    for row in data:
        # Check for valid IMP score
        imp = safe_float(row.get("imp"))
        if imp == 0 and row.get("imp") not in ["0", "0.0"]:
            continue
        
        # Engineer features
        row = engineer_features(row)
        
        # Extract features
        features = []
        valid = True
        for feat in feature_names:
            val = safe_float(row.get(feat))
            features.append(val)
        
        if valid:
            X.append(features)
            y.append(imp)
    
    return np.array(X), np.array(y)


def run_ridge_regression(X: np.ndarray, y: np.ndarray, feature_names: list[str], 
                         alpha: float = 1.0) -> dict:
    """
    Run Ridge Regression and return results.
    """
    if len(X) < 10:
        return None
    
    # Standardize features (important for Ridge)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Fit Ridge Regression
    model = Ridge(alpha=alpha)
    model.fit(X_scaled, y)
    
    # Predictions
    y_pred = model.predict(X_scaled)
    
    # Metrics
    r2 = r2_score(y, y_pred)
    mae = mean_absolute_error(y, y_pred)
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring='r2')
    
    # Build coefficient dictionary (unscaled for interpretability)
    # To get interpretable coefficients, we need to adjust for scaling
    coefficients = {}
    for i, feat in enumerate(feature_names):
        # Adjust coefficient: coef * (y_std / x_std)
        # Since Ridge uses standardized features, raw coefs show relative importance
        raw_coef = model.coef_[i]
        # Store with scale info
        coefficients[feat] = {
            "raw": round(raw_coef, 4),
            "mean": round(scaler.mean_[i], 4) if i < len(scaler.mean_) else 0,
            "std": round(scaler.scale_[i], 4) if i < len(scaler.scale_) else 1,
        }
    
    return {
        "intercept": round(model.intercept_, 4),
        "coefficients": coefficients,
        "r2": round(r2, 4),
        "mae": round(mae, 4),
        "cv_r2_mean": round(np.mean(cv_scores), 4),
        "cv_r2_std": round(np.std(cv_scores), 4),
        "n_samples": len(y),
        "scaler_means": scaler.mean_.tolist(),
        "scaler_scales": scaler.scale_.tolist(),
    }


def get_real_world_coefficients(results: dict, feature_names: list[str]) -> dict:
    """
    Convert standardized coefficients back to real-world scale.
    coef_real = coef_standardized / feature_std
    """
    real_coefs = {}
    for i, feat in enumerate(feature_names):
        raw_coef = results["coefficients"][feat]["raw"]
        std = results["scaler_scales"][i] if i < len(results["scaler_scales"]) else 1
        # Real coefficient = standardized / scale
        real_coef = raw_coef / std if std > 0 else 0
        real_coefs[feat] = round(real_coef, 6)
    
    return real_coefs


# ============================================
# Output Formatting
# ============================================

def format_weights_for_python(all_results: dict[int, dict], feature_names: list[str]) -> str:
    """
    Format results as a Python dictionary for copy-paste into scoring.py.
    """
    output = []
    output.append("# Phase 18: Penta-Role Coefficients")
    output.append("# Generated by solve_formula.py from 6,000+ Stratz samples")
    output.append("# Usage: IMP = intercept + sum(feature * coefficient)")
    output.append("")
    output.append("ROLE_COEFFICIENTS = {")
    
    for pos in sorted(all_results.keys()):
        results = all_results[pos]
        if results is None:
            continue
        
        pos_name = POSITION_NAMES.get(pos, f"POSITION_{pos}")
        pos_desc = POSITION_DESCRIPTIONS.get(pos, "Unknown")
        real_coefs = get_real_world_coefficients(results, feature_names)
        
        output.append(f"    # {pos_desc} (n={results['n_samples']}, R²={results['r2']}, MAE={results['mae']})")
        output.append(f'    "{pos_name}": {{')
        output.append(f'        "intercept": {results["intercept"]},')
        
        # Sort by absolute value for readability
        sorted_coefs = sorted(real_coefs.items(), key=lambda x: abs(x[1]), reverse=True)
        for feat, coef in sorted_coefs:
            if abs(coef) > 0.0001:  # Skip near-zero coefficients
                output.append(f'        "{feat}": {coef},')
        
        output.append("    },")
        output.append("")
    
    output.append("}")
    
    return "\n".join(output)


def print_analysis_summary(all_results: dict[int, dict], feature_names: list[str]) -> None:
    """Print detailed analysis summary."""
    
    print("\n" + "=" * 70)
    print("📊 PENTA-ROLE REGRESSION ANALYSIS RESULTS")
    print("=" * 70)
    
    for pos in sorted(all_results.keys()):
        results = all_results[pos]
        if results is None:
            continue
        
        pos_name = POSITION_NAMES.get(pos, f"Position {pos}")
        pos_desc = POSITION_DESCRIPTIONS.get(pos, "Unknown")
        
        print(f"\n{'─' * 70}")
        print(f"📌 {pos_name}: {pos_desc}")
        print(f"{'─' * 70}")
        print(f"   Samples: {results['n_samples']}")
        print(f"   R² Score: {results['r2']:.4f}")
        print(f"   MAE: {results['mae']:.4f}")
        print(f"   CV R² (5-fold): {results['cv_r2_mean']:.4f} ± {results['cv_r2_std']:.4f}")
        print(f"   Intercept: {results['intercept']}")
        
        # Top positive factors
        real_coefs = get_real_world_coefficients(results, feature_names)
        sorted_by_value = sorted(real_coefs.items(), key=lambda x: x[1], reverse=True)
        
        print(f"\n   🟢 Top POSITIVE Factors:")
        for feat, coef in sorted_by_value[:5]:
            if coef > 0:
                print(f"      {feat}: +{coef:.6f}")
        
        print(f"\n   🔴 Top NEGATIVE Factors:")
        for feat, coef in sorted_by_value[-5:]:
            if coef < 0:
                print(f"      {feat}: {coef:.6f}")


# ============================================
# Main Execution
# ============================================

def main():
    print("=" * 70)
    print("🔬 Phase 18: Penta-Role Regression Analysis")
    print("=" * 70)
    print(f"   Input: {INPUT_FILE}")
    print(f"   Algorithm: Ridge Regression (α={RIDGE_ALPHA})")
    
    # Load data
    print("\n📂 Loading data...")
    data = load_data(INPUT_FILE)
    print(f"   Total records: {len(data)}")
    
    # Split by position
    by_position = defaultdict(list)
    skipped = 0
    
    for row in data:
        pos = get_position(row)
        if pos is not None:
            by_position[pos].append(row)
        else:
            skipped += 1
    
    print(f"\n📊 Distribution by Position:")
    for pos in sorted(by_position.keys()):
        desc = POSITION_DESCRIPTIONS.get(pos, "Unknown")
        print(f"   Position {pos} ({desc}): {len(by_position[pos])} records")
    print(f"   Skipped (unknown position): {skipped}")
    
    # Define features to use
    all_features = BASE_FEATURES + ENGINEERED_FEATURES
    print(f"\n🔧 Features ({len(all_features)}):")
    for feat in all_features:
        print(f"   - {feat}")
    
    # Run regression for each position
    print("\n" + "=" * 70)
    print("🧮 Running Ridge Regression for each position...")
    print("=" * 70)
    
    all_results = {}
    
    for pos in sorted(by_position.keys()):
        pos_data = by_position[pos]
        pos_desc = POSITION_DESCRIPTIONS.get(pos, f"Position {pos}")
        
        print(f"\n⚙️ Training model for {pos_desc}...")
        
        X, y = prepare_features(pos_data, all_features)
        print(f"   Features shape: {X.shape}")
        print(f"   Target range: [{y.min():.1f}, {y.max():.1f}]")
        
        results = run_ridge_regression(X, y, all_features, alpha=RIDGE_ALPHA)
        all_results[pos] = results
        
        if results:
            print(f"   ✅ R² = {results['r2']:.4f}, MAE = {results['mae']:.4f}")
        else:
            print(f"   ❌ Insufficient data")
    
    # Print summary
    print_analysis_summary(all_results, all_features)
    
    # Generate copy-paste code
    print("\n" + "=" * 70)
    print("📋 COPY-PASTE CODE FOR scoring.py")
    print("=" * 70)
    print(format_weights_for_python(all_results, all_features))
    
    # Save to file as well
    output_file = "data/penta_role_coefficients.py"
    with open(output_file, "w") as f:
        f.write(format_weights_for_python(all_results, all_features))
    print(f"\n💾 Coefficients saved to: {output_file}")
    
    # Summary statistics
    print("\n" + "=" * 70)
    print("📈 OVERALL SUMMARY")
    print("=" * 70)
    
    avg_r2 = np.mean([r["r2"] for r in all_results.values() if r])
    avg_mae = np.mean([r["mae"] for r in all_results.values() if r])
    total_samples = sum(r["n_samples"] for r in all_results.values() if r)
    
    print(f"   Total samples used: {total_samples}")
    print(f"   Average R² across roles: {avg_r2:.4f}")
    print(f"   Average MAE across roles: {avg_mae:.4f}")
    
    if avg_r2 > 0.5:
        print("\n   ✅ Good model fit! Ready to use coefficients.")
    elif avg_r2 > 0.3:
        print("\n   ⚠️ Moderate fit. Coefficients are usable but may need tuning.")
    else:
        print("\n   ❌ Low fit. Consider adding more features or data.")


if __name__ == "__main__":
    main()
