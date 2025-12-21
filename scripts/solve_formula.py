#!/usr/bin/env python3
"""
Phase 13: Stratz IMP Formula Solver

Uses regression analysis to reverse-engineer the Stratz IMP formula
from collected ground truth data.

Usage:
    python scripts/solve_formula.py
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any

# Scikit-learn imports
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.linear_model import LinearRegression, Ridge, Lasso
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

# ============================================
# Configuration
# ============================================

INPUT_FILE = "data/stratz_dataset.csv"

# Features to use for regression
# These are the stats that likely influence IMP
CORE_FEATURES = [
    "kills",
    "deaths", 
    "assists",
    "gpm",
    "xpm",
    "hero_damage",
    "tower_damage",
    "networth",
    "level",
    "kda",
    "kills_per_min",
    "deaths_per_min",
    "assists_per_min",
    "hero_damage_per_min",
    "tower_damage_per_min",
    "is_victory",
]

SUPPORT_FEATURES = [
    "kills",
    "deaths",
    "assists", 
    "gpm",
    "xpm",
    "hero_damage",
    "tower_damage",
    "hero_healing",
    "level",
    "kda",
    "kills_per_min",
    "deaths_per_min",
    "assists_per_min",
    "hero_damage_per_min",
    "hero_healing_per_min",
    "is_victory",
]

# ============================================
# Analysis Functions
# ============================================

def load_data(filepath: str) -> pd.DataFrame:
    """Load the Stratz dataset."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {filepath}\n"
            "Run 'python scripts/fetch_stratz_truth.py' first."
        )
    
    df = pd.read_csv(filepath)
    print(f"Loaded {len(df)} records from {filepath}")
    return df


def basic_statistics(df: pd.DataFrame) -> None:
    """Print basic statistics about the dataset."""
    print("\n" + "=" * 60)
    print("DATASET STATISTICS")
    print("=" * 60)
    
    print(f"\nTotal Records: {len(df)}")
    print(f"Unique Matches: {df['match_id'].nunique()}")
    
    # Role distribution
    print(f"\nRole Distribution:")
    role_counts = df["role_type"].value_counts()
    for role, count in role_counts.items():
        print(f"  {role}: {count} ({100*count/len(df):.1f}%)")
    
    # Win/Loss distribution
    print(f"\nWin/Loss Distribution:")
    win_counts = df["is_victory"].value_counts()
    print(f"  Winners: {win_counts.get(1, 0)}")
    print(f"  Losers: {win_counts.get(0, 0)}")
    
    # IMP distribution
    print(f"\nIMP Score Distribution:")
    print(f"  Min: {df['imp'].min():.1f}")
    print(f"  Max: {df['imp'].max():.1f}")
    print(f"  Mean: {df['imp'].mean():.2f}")
    print(f"  Std: {df['imp'].std():.2f}")
    
    # IMP by win/loss
    print(f"\nIMP by Win/Loss:")
    for is_win in [1, 0]:
        subset = df[df["is_victory"] == is_win]
        label = "Winners" if is_win else "Losers"
        print(f"  {label}: mean={subset['imp'].mean():.2f}, std={subset['imp'].std():.2f}")
    
    # IMP by role
    print(f"\nIMP by Role:")
    for role in df["role_type"].unique():
        subset = df[df["role_type"] == role]
        print(f"  {role}: mean={subset['imp'].mean():.2f}, std={subset['imp'].std():.2f}")


def correlation_analysis(df: pd.DataFrame, features: list[str]) -> None:
    """Analyze correlations between features and IMP."""
    print("\n" + "=" * 60)
    print("CORRELATION WITH IMP")
    print("=" * 60)
    
    # Filter to only existing columns
    existing_features = [f for f in features if f in df.columns]
    
    correlations = df[existing_features + ["imp"]].corr()["imp"].drop("imp")
    correlations = correlations.sort_values(key=abs, ascending=False)
    
    print("\nFeatures ranked by correlation with IMP:")
    for feature, corr in correlations.items():
        direction = "+" if corr > 0 else "-"
        strength = "STRONG" if abs(corr) > 0.5 else "MODERATE" if abs(corr) > 0.3 else "WEAK"
        print(f"  {feature:25s}: {direction}{abs(corr):.3f} ({strength})")


def run_regression(
    df: pd.DataFrame, 
    features: list[str], 
    target: str = "imp",
    model_name: str = "Linear Regression",
    model=None
) -> dict[str, Any]:
    """Run regression analysis and return results."""
    
    # Filter to only existing columns
    existing_features = [f for f in features if f in df.columns]
    
    if len(existing_features) < len(features):
        missing = set(features) - set(existing_features)
        print(f"  Warning: Missing features: {missing}")
    
    # Prepare data
    X = df[existing_features].fillna(0)
    y = df[target]
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Scale features for regularized models
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Use provided model or default to Linear Regression
    if model is None:
        model = LinearRegression()
    
    # Train model
    model.fit(X_train_scaled, y_train)
    
    # Predictions
    y_pred = model.predict(X_test_scaled)
    
    # Metrics
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    
    # Cross-validation
    cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=5, scoring="r2")
    
    results = {
        "model_name": model_name,
        "model": model,
        "scaler": scaler,
        "features": existing_features,
        "mse": mse,
        "rmse": rmse,
        "mae": mae,
        "r2": r2,
        "cv_r2_mean": cv_scores.mean(),
        "cv_r2_std": cv_scores.std(),
    }
    
    return results


def print_coefficients(results: dict, df: pd.DataFrame) -> None:
    """Print the learned coefficients (weights) for each feature."""
    model = results["model"]
    features = results["features"]
    scaler = results["scaler"]
    
    print(f"\n--- {results['model_name']} ---")
    print(f"R² Score: {results['r2']:.4f}")
    print(f"RMSE: {results['rmse']:.2f}")
    print(f"MAE: {results['mae']:.2f}")
    print(f"Cross-Val R² (5-fold): {results['cv_r2_mean']:.4f} ± {results['cv_r2_std']:.4f}")
    
    # Get coefficients (for linear models)
    if hasattr(model, "coef_"):
        print(f"\nLearned Coefficients (Weights):")
        print("-" * 50)
        
        # Get raw coefficients and scale information
        coefs = model.coef_
        intercept = model.intercept_ if hasattr(model, "intercept_") else 0
        
        # Create coefficient dataframe
        coef_df = pd.DataFrame({
            "feature": features,
            "coefficient": coefs,
            "abs_coefficient": np.abs(coefs)
        }).sort_values("abs_coefficient", ascending=False)
        
        # Calculate approximate real-world impact
        # (coefficient * typical standard deviation of feature)
        stds = scaler.scale_
        
        print(f"\nIntercept: {intercept:.4f}")
        print(f"\nFeature Weights (sorted by importance):")
        
        for idx, row in coef_df.iterrows():
            feature = row["feature"]
            coef = row["coefficient"]
            feat_idx = features.index(feature)
            feature_std = stds[feat_idx]
            
            # Impact = coef * 1_std_change
            impact = coef * feature_std
            
            direction = "+" if coef > 0 else ""
            print(f"  {feature:25s}: {direction}{coef:.4f}  (1σ impact: {direction}{impact:.2f})")
        
        # Generate the formula
        print(f"\n--- ESTIMATED FORMULA ---")
        formula_parts = [f"{intercept:.2f}"]
        for _, row in coef_df.head(8).iterrows():
            feature = row["feature"]
            coef = row["coefficient"]
            feat_idx = features.index(feature)
            feature_std = stds[feat_idx]
            feature_mean = scaler.mean_[feat_idx]
            
            # Convert to raw feature scale
            raw_coef = coef / max(feature_std, 0.001)
            sign = "+" if raw_coef > 0 else "-"
            print(f"    {sign} ({feature} * {abs(raw_coef):.6f})")
    
    # For tree-based models, show feature importances
    elif hasattr(model, "feature_importances_"):
        print(f"\nFeature Importances:")
        print("-" * 50)
        
        importance_df = pd.DataFrame({
            "feature": features,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)
        
        for _, row in importance_df.iterrows():
            importance_bar = "█" * int(row["importance"] * 50)
            print(f"  {row['feature']:25s}: {row['importance']:.4f} {importance_bar}")


def analyze_by_role(df: pd.DataFrame) -> None:
    """Run separate analyses for Cores and Supports."""
    print("\n" + "=" * 60)
    print("REGRESSION ANALYSIS BY ROLE")
    print("=" * 60)
    
    # Filter to cores
    cores = df[df["role_type"] == "core"]
    if len(cores) > 50:
        print(f"\n{'='*60}")
        print(f"CORE PLAYERS (n={len(cores)})")
        print(f"{'='*60}")
        
        # Linear Regression
        lr_results = run_regression(
            cores, CORE_FEATURES, 
            model_name="Linear Regression"
        )
        print_coefficients(lr_results, cores)
        
        # Ridge Regression (regularized)
        ridge_results = run_regression(
            cores, CORE_FEATURES,
            model_name="Ridge Regression",
            model=Ridge(alpha=1.0)
        )
        print_coefficients(ridge_results, cores)
        
        # Random Forest (for feature importance)
        rf_results = run_regression(
            cores, CORE_FEATURES,
            model_name="Random Forest",
            model=RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
        )
        print_coefficients(rf_results, cores)
    else:
        print(f"\nNot enough core players ({len(cores)}) for regression.")
    
    # Filter to supports
    supports = df[df["role_type"] == "support"]
    if len(supports) > 50:
        print(f"\n{'='*60}")
        print(f"SUPPORT PLAYERS (n={len(supports)})")
        print(f"{'='*60}")
        
        # Linear Regression
        lr_results = run_regression(
            supports, SUPPORT_FEATURES,
            model_name="Linear Regression"
        )
        print_coefficients(lr_results, supports)
        
        # Ridge Regression
        ridge_results = run_regression(
            supports, SUPPORT_FEATURES,
            model_name="Ridge Regression", 
            model=Ridge(alpha=1.0)
        )
        print_coefficients(ridge_results, supports)
        
        # Random Forest
        rf_results = run_regression(
            supports, SUPPORT_FEATURES,
            model_name="Random Forest",
            model=RandomForestRegressor(n_estimators=100, random_state=42, max_depth=10)
        )
        print_coefficients(rf_results, supports)
    else:
        print(f"\nNot enough support players ({len(supports)}) for regression.")


def generate_weight_recommendations(df: pd.DataFrame) -> None:
    """Generate recommended weights for our IMP engine based on the analysis."""
    print("\n" + "=" * 60)
    print("RECOMMENDED WEIGHTS FOR IMPETUS")
    print("=" * 60)
    
    cores = df[df["role_type"] == "core"]
    supports = df[df["role_type"] == "support"]
    
    print("""
Based on the regression analysis, here are recommended weight adjustments
for the Impetus IMP Engine:

CORE PLAYERS:
""")
    
    if len(cores) > 50:
        # Run a simple ridge regression to get stable coefficients
        existing_features = [f for f in CORE_FEATURES if f in cores.columns]
        X = cores[existing_features].fillna(0)
        y = cores["imp"]
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = Ridge(alpha=1.0)
        model.fit(X_scaled, y)
        
        # Map coefficients to our weight format
        coefs = dict(zip(existing_features, model.coef_))
        
        print("  Stat                 | Stratz Influence | Suggested Weight")
        print("  " + "-" * 55)
        
        for feature in ["kills", "deaths", "assists", "gpm", "tower_damage", "hero_damage"]:
            if feature in coefs:
                influence = coefs[feature]
                direction = "+" if influence > 0 else "-"
                
                # Normalize to weight scale (0.5 to 3.0)
                suggested = max(0.5, min(3.0, abs(influence) / 5 + 1.0))
                
                print(f"  {feature:20s} | {direction}{abs(influence):6.3f}         | {suggested:.1f}x")
    
    print("""
SUPPORT PLAYERS:
""")
    
    if len(supports) > 50:
        existing_features = [f for f in SUPPORT_FEATURES if f in supports.columns]
        X = supports[existing_features].fillna(0)
        y = supports["imp"]
        
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        model = Ridge(alpha=1.0)
        model.fit(X_scaled, y)
        
        coefs = dict(zip(existing_features, model.coef_))
        
        print("  Stat                 | Stratz Influence | Suggested Weight")
        print("  " + "-" * 55)
        
        for feature in ["kills", "deaths", "assists", "hero_healing", "tower_damage"]:
            if feature in coefs:
                influence = coefs[feature]
                direction = "+" if influence > 0 else "-"
                suggested = max(0.3, min(2.0, abs(influence) / 5 + 0.5))
                
                print(f"  {feature:20s} | {direction}{abs(influence):6.3f}         | {suggested:.1f}x")


# ============================================
# Main Execution
# ============================================

def main():
    print("=" * 60)
    print("Phase 13: Stratz IMP Formula Solver")
    print("=" * 60)
    
    # Load data
    try:
        df = load_data(INPUT_FILE)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return
    
    # Basic statistics
    basic_statistics(df)
    
    # Correlation analysis
    all_features = list(set(CORE_FEATURES + SUPPORT_FEATURES))
    correlation_analysis(df, all_features)
    
    # Regression by role
    analyze_by_role(df)
    
    # Generate recommendations
    generate_weight_recommendations(df)
    
    print("\n" + "=" * 60)
    print("Analysis Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
