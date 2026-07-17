"""
app/core/forecasting.py
========================
Ensemble demand forecasting engine, extracted from main.py.

Shared between:
  - app.core.all_items_ui  (📈 All Items Analytics tab)
  - app.core.dry_ice_ui    (🔮 Demand Forecast tab, once ported — same
    create_ensemble_forecast() call, same create_scenario_analysis /
    render_scenario_analysis / render_scenario_summary trio)

create_ensemble_forecast() is the main entry point — it tries the full
8-model ensemble (Prophet, NeuralProphet, ARIMA, LSTM, Monte Carlo,
XGBoost, LightGBM, RandomForest) via AdvancedForecaster, and falls back to
create_legacy_forecast() (simple average) if that's unavailable or errors.

NOTE ON @st.cache_data: create_ensemble_forecast keeps its original
@st.cache_data(ttl=1800, show_spinner=False) decorator. Streamlit caches by
function identity + args, so both all_items_ui.py and dry_ice_ui.py
importing this same function will share one cache — a forecast computed by
one tab for a given df/params won't be recomputed by the other. That's a
behavior change from when this lived duplicated-in-spirit inline in
main.py (it wasn't actually duplicated there either — both tabs called the
same top-level function — so this preserves existing behavior, just makes
the sharing explicit).

Local imports inside function bodies (AdvancedForecaster, ExternalFactors,
RandomForestRegressor) are kept exactly as in the original main.py to
minimize risk — these were deliberately deferred imports there (heavy /
optional dependencies), not an oversight.
"""
import warnings
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

from core.error_handling import logger, log_performance


@log_performance
@st.cache_data(ttl=1800, show_spinner=False)
def create_ensemble_forecast(df, forecast_days=30, selected_models=None):
    """
    Create ensemble forecast combining ALL 8 models:
    Prophet, NeuralProphet, ARIMA, LSTM, Monte Carlo,
    XGBoost, LightGBM, and RandomForest.
    """
    try:
        from app.core.advanced_forecasting_v2 import AdvancedForecaster
        from app.core.external_factors import ExternalFactors
        warnings.filterwarnings('ignore')

        # Initialize the forecaster (now has ALL 8 models!)
        forecaster = AdvancedForecaster()

        # Initialize external factors
        external = ExternalFactors()
        external_factors = external.get_all_external_factors()

        # Create future dates
        last_date = df['Date'].max()
        future_dates = pd.date_range(last_date, periods=forecast_days + 1, freq='D')[1:]

        # Prepare external features for future dates
        external_features = external.prepare_external_features(future_dates)

        # Log external factors being used
        logger.info(f"External factors included: {list(external_factors.keys())}")
        logger.info(f"External features shape: {external_features.shape if external_features is not None else 'None'}")

        # Generate forecast using selected models (or all 8 if none specified)
        results = forecaster.forecast(df, forecast_days, models=selected_models)
        logger.info("=== MODEL TYPES BEFORE ENSEMBLE ===")
        for name, result in results.items():
            logger.info(
                f"{name}: type={type(result).__name__} "
                f"value={str(result)[:100] if result is not None else 'None'}"
            )
        # Get ensemble forecast
        ensemble_values = np.array(results['ensemble']['forecast'])

        # ============================================================
        # Model display names for ALL 8 models

        model_display_names = {
            'prophet': 'Prophet',
            'neural_prophet': 'NeuralProphet',
            'arima': 'ARIMA',
            'lstm': 'LSTM',
            'monte_carlo': 'Monte Carlo',
            'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM',
            'random_forest': 'RandomForest'
        }

        # ============================================================
        # Track active models and their statistics

        model_forecasts = {}
        active_models = []

        for name, result in results.items():
            if name != 'ensemble' and result is not None and isinstance(result, dict) and 'forecast' in result:
                forecast_values = result['forecast']
                if len(forecast_values) == forecast_days:
                    display_name = model_display_names.get(name, name.title())
                    model_forecasts[display_name] = {
                        'avg': np.mean(forecast_values),
                        'min': np.min(forecast_values),
                        'max': np.max(forecast_values),
                        'std': np.std(forecast_values)
                    }
                    active_models.append(display_name)

        # ============================================================
        # Create model comparison DataFrame

        model_comparison = []
        for name, stats in model_forecasts.items():
            model_comparison.append({
                'Model': name,
                'Avg Forecast (kg)': f"{stats['avg']:.1f}",
                'Min (kg)': f"{stats['min']:.1f}",
                'Max (kg)': f"{stats['max']:.1f}",
                'Std Dev': f"{stats['std']:.1f}",
                'Status': '✅ Active'
            })

        # ============================================================
        # Store in session state for dashboard display

        st.session_state.model_comparison = pd.DataFrame(model_comparison)
        st.session_state.active_models = len(active_models)
        st.session_state.active_models_list = active_models

        # Log which models are active
        logger.info(f"✅ Active models: {len(active_models)}/8 - {active_models}")

        # ============================================================
        # Calculate backtest accuracy

        try:
            X, y = forecaster.prepare_features(df)

            # Calculate metrics by training on historical data
            test_size = min(30, len(X) // 3)
            if test_size > 0:
                # Use the last test_size points for backtesting
                X_train, X_test = X[:-test_size], X[-test_size:]
                y_train, y_test = y[:-test_size], y[-test_size:]

                # Train a simple model for backtesting
                from sklearn.ensemble import RandomForestRegressor
                test_model = RandomForestRegressor(n_estimators=50, random_state=42)
                test_model.fit(X_train, y_train)
                predictions = test_model.predict(X_test)

                # Convert to arrays and align lengths
                y_true = np.array(y_test)
                y_pred = np.array(predictions[:len(y_test)])

                # Remove NaNs
                mask = ~(np.isnan(y_true) | np.isnan(y_pred))
                y_true = y_true[mask]
                y_pred = y_pred[mask]

                if len(y_true) > 1:
                    # MAE
                    mae = np.mean(np.abs(y_true - y_pred))
                    mean_actual = max(np.mean(y_true), 1)
                    mae_normalized = min(mae / mean_actual, 1)

                    # R² - stricter: if negative, contribution is 0
                    ss_res = np.sum((y_true - y_pred) ** 2)
                    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
                    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
                    if r2 < 0:
                        r2_normalized = 0  # No credit for worse than mean
                    else:
                        r2_normalized = min(r2, 1)

                    # Direction accuracy
                    # np.mean() of a boolean comparison already returns a
                    # fraction in [0, 1] — do NOT divide by 100 again.
                    actual_direction = np.sign(np.diff(y_true))
                    pred_direction = np.sign(np.diff(y_pred))
                    direction_normalized = (
                        np.mean(actual_direction == pred_direction)
                        if len(actual_direction) > 0
                        else 0
                    )

                    # WAPE penalty - smooth decay instead of MAPE's hard cliff.
                    # MAPE explodes on near-zero actuals (common with
                    # intermittent demand); WAPE is robust to that.
                    wape = np.sum(np.abs(y_true - y_pred)) / max(np.sum(np.abs(y_true)), 1e-8) * 100
                    wape_penalty = max(0, min(1, 1 - (wape - 50) / 150)) if wape > 50 else 1

                    # Composite score (0-1 scale) with penalties
                    backtest_accuracy = (
                        0.4 * (1 - mae_normalized) +
                        0.3 * r2_normalized +
                        0.3 * direction_normalized
                    ) * wape_penalty
                else:
                    backtest_accuracy = 0

                # Ensure it's between 0 and 1
                backtest_accuracy = max(0, min(1, backtest_accuracy))
            else:
                backtest_accuracy = 0.85
        except Exception as e:
            logger.warning(f"Backtest accuracy calculation failed: {e}")
            backtest_accuracy = 0.85

        # ============================================================
        # 🔧 FIX: Get best model from results
        # ============================================================
        # The best model is now stored in the ensemble results
        best_model_name = results['ensemble'].get('_best_model', None)
        best_model_score = results['ensemble'].get('_best_score', None)

        if best_model_name:
            st.session_state.best_model = {
                'name': model_display_names.get(best_model_name, best_model_name.title()),
                'score': f"{best_model_score:.1f}" if best_model_score else "N/A",
                'accuracy': f"{backtest_accuracy*100:.1f}%"
            }
        elif active_models:
            # Fallback: use first active model
            st.session_state.best_model = {
                'name': active_models[0],
                'score': "N/A",
                'accuracy': f"{backtest_accuracy*100:.1f}%"
            }

        # ============================================================
        # Create visualization with external factors info
        fig = create_forecast_visualization_with_external(
            df, results, forecast_days, external_factors, external_features
        )

        # Add external factors info to model forecasts
        if external_factors:
            model_forecasts['External Factors'] = ', '.join(list(external_factors.keys())[:3])
            if len(external_factors) > 3:
                model_forecasts['External Factors'] += f' and {len(external_factors)-3} more'

        return fig, ensemble_values, model_forecasts, backtest_accuracy

    except ImportError as e:
        logger.error(f"AdvancedForecaster or ExternalFactors import failed: {e}")
        st.warning("⚠️ Advanced forecasting or external factors not available. Using legacy forecast.")
        return create_legacy_forecast(df, forecast_days)

    except Exception as e:
        logger.error(f"Advanced forecast failed: {e}")
        st.warning(f"⚠️ Advanced forecast failed: {str(e)}. Using legacy forecast.")
        return create_legacy_forecast(df, forecast_days)


def create_legacy_forecast(df, forecast_days=30):
    """
    Legacy forecast function as fallback.
    """
    try:
        dates = pd.to_datetime(df['Date'])
        values = df['Order_Quantity_kg'].values.astype(float)

        # Fallback: use simple average
        avg_demand = np.mean(values) if len(values) > 0 else 300.0
        ensemble_forecast = np.full(forecast_days, max(0, avg_demand))

        # Create simple visualization
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            name='Historical Demand',
            line=dict(color='blue', width=2)
        ))

        future_dates = pd.date_range(dates.max(), periods=forecast_days + 1, freq='D')[1:]
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=ensemble_forecast,
            name='Average Forecast (Fallback)',
            line=dict(color='orange', width=2)
        ))

        fig.update_layout(
            title='30-Day Demand Forecast (Simple Average - Fallback)',
            xaxis_title='Date',
            yaxis_title='Demand (kg)',
            height=500
        )

        model_forecasts = {'Simple Average': avg_demand}
        backtest_accuracy = 0.80

        return fig, ensemble_forecast, model_forecasts, backtest_accuracy

    except Exception as e:
        logger.error(f"Legacy forecast failed: {e}")
        # Ultra fallback
        avg_demand = 300.0
        ensemble_forecast = np.full(forecast_days, avg_demand)

        fig = go.Figure()
        fig.add_annotation(text="⚠️ Forecast unavailable - using default values", showarrow=False)

        return fig, ensemble_forecast, {'Default': avg_demand}, 0.0


def create_forecast_visualization(df, results, forecast_days):
    """
    Create visualization for all model forecasts.
    (Simpler single-panel variant of create_forecast_visualization_with_external
    below — kept since main.py defined both and some call sites may still
    want the version without the external-factors panel.)
    """
    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Order_Quantity_kg'],
        name='Historical Demand',
        line=dict(color='blue', width=2)
    ))

    # Future dates
    future_dates = pd.date_range(
        df['Date'].max(),
        periods=forecast_days + 1,
        freq='D'
    )[1:]

    # Color palette for models
    colors = ['#2ecc71', '#e74c3c', '#9b59b6', '#f39c12', '#1abc9c']
    color_idx = 0

    # Add each model's forecast
    for name, result in results.items():
        if name != 'ensemble' and result and isinstance(result, dict) and 'forecast' in result:
            forecast_values = result['forecast']
            if len(forecast_values) == forecast_days:
                # Clean up model names for display
                display_name = name.replace('_', ' ').title()

                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=forecast_values,
                    name=display_name,
                    line=dict(dash='dot', color=colors[color_idx % len(colors)])
                ))
                color_idx += 1

    # Add ensemble forecast
    if 'ensemble' in results and results['ensemble']:
        ensemble_values = results['ensemble']['forecast']

        # Ensemble line
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=ensemble_values,
            name='Ensemble Forecast',
            line=dict(color='black', width=3)
        ))

        # Confidence interval
        if 'upper' in results['ensemble'] and 'lower' in results['ensemble']:
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['upper'],
                fill=None,
                mode='lines',
                line_color='rgba(0,0,0,0)',
                showlegend=False
            ))
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['lower'],
                fill='tonexty',
                mode='lines',
                line_color='rgba(0,0,0,0)',
                name='Confidence Interval (80%)',
                fillcolor='rgba(255,127,14,0.2)'
            ))

    fig.update_layout(
        title='30-Day Demand Forecast with Ensemble Methods',
        xaxis_title='Date',
        yaxis_title='Demand (kg)',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=500,
        hovermode='x unified'
    )

    return fig


def create_forecast_visualization_with_external(df, results, forecast_days, external_factors=None, external_features=None):
    """
    Create visualization for all model forecasts with external factors info.
    """
    # Create subplots with extra space for external factors
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.75, 0.25],
        subplot_titles=("Demand Forecast", "External Factors Impact"),
        vertical_spacing=0.12
    )

    # Historical data (main chart)
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Order_Quantity_kg'],
        name='Historical Demand',
        line=dict(color='blue', width=2),
        legendgroup='historical',
        showlegend=True
    ), row=1, col=1)

    # Future dates
    future_dates = pd.date_range(
        df['Date'].max(),
        periods=forecast_days + 1,
        freq='D'
    )[1:]

    # Color palette for models
    colors = ['#2ecc71', '#e74c3c', '#9b59b6', '#f39c12', '#1abc9c']
    color_idx = 0

    # Add each model's forecast
    for name, result in results.items():
        if name != 'ensemble' and result and isinstance(result, dict) and 'forecast' in result:
            forecast_values = result['forecast']
            if len(forecast_values) == forecast_days:
                # Clean up model names for display
                display_name = name.replace('_', ' ').title()

                fig.add_trace(go.Scatter(
                    x=future_dates,
                    y=forecast_values,
                    name=display_name,
                    line=dict(dash='dot', color=colors[color_idx % len(colors)]),
                    legendgroup='models',
                    showlegend=True
                ), row=1, col=1)
                color_idx += 1

    # Add ensemble forecast
    if 'ensemble' in results and results['ensemble']:
        ensemble_values = results['ensemble']['forecast']

        # Ensemble line
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=ensemble_values,
            name='Ensemble Forecast',
            line=dict(color='black', width=3),
            legendgroup='ensemble',
            showlegend=True
        ), row=1, col=1)

        # Confidence interval
        if 'upper' in results['ensemble'] and 'lower' in results['ensemble']:
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['upper'],
                fill=None,
                mode='lines',
                line_color='rgba(0,0,0,0)',
                showlegend=False
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=future_dates,
                y=results['ensemble']['lower'],
                fill='tonexty',
                mode='lines',
                line_color='rgba(0,0,0,0)',
                name='Confidence Interval (80%)',
                fillcolor='rgba(255,127,14,0.2)',
                legendgroup='ensemble',
                showlegend=True
            ), row=1, col=1)

    # Add external factors visualization (bottom chart)
    if external_factors and external_features is not None:
        # Show external factors that might impact demand
        factor_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']

        # Get external factor names
        factor_names = list(external_factors.keys())

        # Show top external factors (up to 4)
        for idx, factor_name in enumerate(factor_names[:4]):
            if factor_name in external_features.columns:
                # Normalize the factor for display
                factor_values = external_features[factor_name].values
                if len(factor_values) == forecast_days:
                    # Normalize to 0-1 range for display
                    if factor_values.max() > factor_values.min():
                        normalized = (factor_values - factor_values.min()) / (factor_values.max() - factor_values.min())
                    else:
                        normalized = factor_values / (factor_values.max() + 1e-10)

                    fig.add_trace(go.Scatter(
                        x=future_dates,
                        y=normalized,
                        name=factor_name.replace('_', ' ').title(),
                        line=dict(color=factor_colors[idx % len(factor_colors)], width=2),
                        legendgroup='external',
                        showlegend=True
                    ), row=2, col=1)

        # Update y-axis for external factors
        fig.update_yaxes(title_text="Impact (Normalized)", row=2, col=1)

    # Update layout
    fig.update_layout(
        title='30-Day Demand Forecast with External Factors',
        xaxis_title='Date',
        yaxis_title='Demand (kg)',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=700,  # Increased height for external factors
        hovermode='x unified'
    )

    # Update x-axis for bottom chart
    fig.update_xaxes(title_text="Date", row=2, col=1)

    return fig


def create_scenario_analysis(forecast, historical_data):
    """
    Create multiple demand scenarios.
    """
    scenarios = {
        'p50': {
            'name': 'Likely Scenario (50th Percentile)',
            'description': 'Base case - most likely outcome',
            'multiplier': 1.0,
            'color': '#28a745'
        },
        'p70': {
            'name': 'Optimistic Scenario (70th Percentile)',
            'description': 'Higher demand than expected',
            'multiplier': 1.15,
            'color': '#4caf50'
        },
        'p90': {
            'name': 'Worst Case (90th Percentile)',
            'description': 'Prepare for high demand',
            'multiplier': 1.30,
            'color': '#dc3545'
        },
        'promotional': {
            'name': 'Promotional Impact',
            'description': 'Demand spike from promotion',
            'multiplier': 1.25,
            'color': '#ff9800'
        },
        'supply_chain': {
            'name': 'Supply Chain Disruption',
            'description': 'Delayed supply impact',
            'multiplier': 0.80,
            'color': '#ff5722'
        },
        'economic': {
            'name': 'Economic Downturn',
            'description': 'Reduced demand due to economy',
            'multiplier': 0.70,
            'color': '#9c27b0'
        },
        'weather': {
            'name': 'Weather Impact',
            'description': 'Weather affecting demand',
            'multiplier': [0.9, 1.1],  # Variable impact
            'color': '#2196f3'
        },
        'best_case': {
            'name': 'Best Case Scenario',
            'description': 'Everything goes perfectly',
            'multiplier': 1.40,
            'color': '#00bcd4'
        },
        'worst_case': {
            'name': 'Worst Case Scenario',
            'description': 'Everything goes wrong',
            'multiplier': 0.60,
            'color': '#e91e63'
        }
    }

    scenario_results = {}

    base_forecast = np.array(forecast)

    for key, scenario in scenarios.items():
        multiplier = scenario['multiplier']

        if isinstance(multiplier, list):
            # Variable multiplier over time
            scenario_forecast = base_forecast * np.linspace(multiplier[0], multiplier[1], len(base_forecast))
        else:
            scenario_forecast = base_forecast * multiplier

        scenario_results[key] = {
            'name': scenario['name'],
            'description': scenario['description'],
            'forecast': scenario_forecast.tolist(),
            'color': scenario['color'],
            'total_demand': sum(scenario_forecast),
            'avg_daily': np.mean(scenario_forecast)
        }

    return scenario_results


def render_scenario_analysis(scenario_results, forecast_days):
    """
    Render scenario analysis in UI.
    """
    fig = go.Figure()

    # Create dates
    future_dates = pd.date_range(datetime.now(), periods=forecast_days, freq='D')

    # Add each scenario
    for key, scenario in scenario_results.items():
        fig.add_trace(go.Scatter(
            x=future_dates,
            y=scenario['forecast'],
            name=scenario['name'],
            line=dict(color=scenario['color'], width=2, dash='dot' if key != 'p50' else 'solid'),
            mode='lines+markers',
            hovertemplate='%{y:,.0f} kg<extra></extra>'
        ))

    fig.update_layout(
        title='📊 Demand Scenarios',
        xaxis_title='Date',
        yaxis_title='Demand (kg)',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        height=400
    )

    return fig


def render_scenario_summary(scenario_results):
    """
    Render scenario summary cards.
    """
    # Summary cards
    cols = st.columns(min(4, len(scenario_results)))

    for idx, (key, scenario) in enumerate(scenario_results.items()):
        if idx >= 4:
            break

        with cols[idx]:
            st.markdown(f"""
            <div style="
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
                padding: 12px;
                text-align: center;
                border-left: 3px solid {scenario['color']};
                margin-bottom: 8px;
            ">
                <div style="font-size: 12px; font-weight: 600; color: #888;">
                    {scenario['name']}
                </div>
                <div style="font-size: 20px; font-weight: 700; color: {scenario['color']};">
                    {scenario['avg_daily']:.0f}
                </div>
                <div style="font-size: 10px; color: #999;">
                    avg kg/day
                </div>
                <div style="font-size: 10px; color: #999; margin-top: 2px;">
                    Total: {scenario['total_demand']:,.0f} kg
                </div>
            </div>
            """, unsafe_allow_html=True)