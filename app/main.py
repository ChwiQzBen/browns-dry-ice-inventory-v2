from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import norm
import sys
import os
from pathlib import Path
import sqlite3
import math
from scipy import stats
from statsmodels.tsa.arima.model import ARIMA
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error
from core.analyzer import DryIceAnalyzer
from core.inventory_tracker import InventoryTracker
from core.mobile_interface import MobileInterface
from core.smart_alerts import SmartAlerts
from core.predictive_maintenance import PredictiveMaintenance
from core.system_integrations import SystemIntegrations
from core.report_generator import ReportGenerator
import warnings
DATABASE_FILE = 'dry_ice.db'
BAD_DATE = '2_024-09-26'
GOOD_DATE = '2024-09-26'
# ---------------------

def fix_order_date():
    """Finds a specific incorrect date in the historical_orders table and updates it."""

    if not os.path.exists(DATABASE_FILE):
        print(f"Error: Database file '{DATABASE_FILE}' not found.")
        return

    conn = sqlite3.connect(DATABASE_FILE)
    c = conn.cursor()

    print(f"Connected to database '{DATABASE_FILE}'.")

    try:
        # First, check if the bad record exists
        c.execute("SELECT id FROM historical_orders WHERE date = ?", (BAD_DATE,))
        record = c.fetchone()

        if not record:
            print(f"No record found with the date '{BAD_DATE}'. It might already be fixed.")
            return

        print(f"Found record with incorrect date '{BAD_DATE}'. Attempting to update...")

        # This is the core command: UPDATE the row WHERE the date matches the bad one.
        c.execute("UPDATE historical_orders SET date = ? WHERE date = ?", (GOOD_DATE, BAD_DATE))

        # Commit the changes to save them permanently to the file.
        conn.commit()

        # Check how many rows were affected. It should be 1.
        if c.rowcount > 0:
            print(f"Success! Updated {c.rowcount} row(s) from '{BAD_DATE}' to '{GOOD_DATE}'.")
        else:
            print("Update executed, but no rows were changed. This is unexpected.")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        print("Rolling back any changes.")
        conn.rollback() # Undo changes if there was an error

    finally:
        # Always close the connection.
        conn.close()
        print("Database connection closed.")


st.set_page_config(
    page_title="Browns Food Co - Dry Ice Inventory Optimizer",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class Constants:
    PRICE_PER_KG = 146.55
    CONTAINER_SIZE = 150
    TRANSPORT_COST = 1741.94
    HOLDING_RATE = 0.03
    SUB_LOSS_RANGE = (1.51, 3.03)
    LEAD_TIME_DAYS = 1
    SERVICE_LEVEL = 0.95
    IMPLEMENTATION_COST = 50000

constants = Constants()

# SQLite Database Setup
def init_db():
    """Initialize SQLite database and create/update tables if they don't exist"""
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    # --- Create/Update transactions table ---
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  type TEXT NOT NULL,
                  quantity REAL NOT NULL,
                  item TEXT NOT NULL,
                  description TEXT,
                  notes TEXT,
                  analysis_period TEXT)''') # ADD analysis_period column
    # Add column if it doesn't exist (for existing databases)
    c.execute("PRAGMA table_info(transactions)")
    if 'analysis_period' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE transactions ADD COLUMN analysis_period TEXT")

    # --- Create/Update inventory table (remains unchanged) ---
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  stock_level REAL NOT NULL,
                  transaction_id INTEGER,
                  FOREIGN KEY(transaction_id) REFERENCES transactions(id))''')

    # --- Create/Update historical_orders table ---
    c.execute('''CREATE TABLE IF NOT EXISTS historical_orders
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT NOT NULL,
                  order_quantity REAL NOT NULL,
                  analysis_period TEXT)''') # ADD analysis_period column
    # Add column if it doesn't exist (for existing databases)
    c.execute("PRAGMA table_info(historical_orders)")
    if 'analysis_period' not in [col[1] for col in c.fetchall()]:
        c.execute("ALTER TABLE historical_orders ADD COLUMN analysis_period TEXT")

    conn.commit()
    conn.close()

def clear_transactions_from_db():
        """
        Permanently delete all records from the transactions, inventory,
        AND historical_orders tables to perform a full reset.
        """
        conn = sqlite3.connect('dry_ice.db')
        c = conn.cursor()

        try:
            # Use DELETE to empty the tables. This is a permanent action.
            c.execute('DELETE FROM transactions')
            c.execute('DELETE FROM inventory')
            c.execute('DELETE FROM historical_orders') # --- ADD THIS LINE ---

            # Good practice: Reset the auto-increment counter for the primary keys
            c.execute('DELETE FROM sqlite_sequence WHERE name="transactions"')
            c.execute('DELETE FROM sqlite_sequence WHERE name="inventory"')
            c.execute('DELETE FROM sqlite_sequence WHERE name="historical_orders"') # --- AND THIS LINE ---

            conn.commit()
            # The success message is now part of the button logic, so it's okay to remove it here

        except sqlite3.Error as e:
            st.error(f"Database error while clearing transactions: {e}")
        finally:
            conn.close()

def add_transaction_to_db(transaction_type, quantity, description, date, period):
    """Add transaction to SQLite database for a specific analysis period"""
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    transaction = {
        'date': date.isoformat(),
        'type': transaction_type,
        'quantity': quantity,
        'item': 'Dry Ice',
        'description': description,
        'notes': f"{description} - {quantity} kg",
        'analysis_period': period  # Add period to transaction data
    }

    c.execute('''INSERT INTO transactions
                 (date, type, quantity, item, description, notes, analysis_period)
                 VALUES (:date, :type, :quantity, :item, :description, :notes, :analysis_period)''',
              transaction)

    transaction_id = c.lastrowid

    # Inventory updates as before
    if transaction_type == 'usage':
        c.execute('''INSERT INTO inventory (date, stock_level, transaction_id)
                     VALUES (?, (SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1) - ?, ?)''',
                  (date.isoformat(), quantity, transaction_id))
    elif transaction_type == 'receipt':
        c.execute('''INSERT INTO inventory (date, stock_level, transaction_id)
                     VALUES (?, (SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1) + ?, ?)''',
                  (date.isoformat(), quantity, transaction_id))

        # Only record the historical order for the current period
        c.execute('''INSERT INTO historical_orders (date, order_quantity, analysis_period)
                     VALUES (?, ?, ?)''',
                  (date.isoformat(), quantity, period))

    conn.commit()
    conn.close()
    return transaction_id

def get_transactions_from_db(period):
    """Retrieve all transactions from SQLite database for a specific period"""
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''SELECT date, type, quantity, item, description, notes
                 FROM transactions WHERE analysis_period = ? ORDER BY date DESC''', (period,))
    transactions = c.fetchall()

    conn.close()

    transaction_list = []
    for t in transactions:
        transaction_list.append({
            'date': datetime.fromisoformat(t[0]),
            'type': t[1], 'quantity': t[2], 'item': t[3],
            'description': t[4], 'notes': t[5]
        })

    return transaction_list

def get_current_stock_from_db():
    """Get the current stock level from SQLite database"""
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''SELECT stock_level FROM inventory ORDER BY date DESC LIMIT 1''')
    result = c.fetchone()

    conn.close()

    return result[0] if result else 0

def update_current_stock_in_db(new_stock, date):
    """Update the current stock level in SQLite database"""
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''INSERT INTO inventory (date, stock_level)
                 VALUES (?, ?)''',
              (date.isoformat(), new_stock))

    conn.commit()
    conn.close()

def seed_historical_data():
    """
    Seed the database with historical order data if empty, and run a one-time
    update to tag any existing untagged records.
    """
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    # --- Part 1: Seed data only if the table is completely empty ---
    c.execute('''SELECT COUNT(*) FROM historical_orders''')
    count = c.fetchone()[0]

    if count == 0:
        print("Database is empty. Seeding historical data for 2024/2025...")
        # This historical data is based on the list you provided, containing 151 orders.
        base_historical_data = [
            ('2025-06-30', 450.00), ('2025-06-27', 300.00), ('2025-06-26', 150.00),
            ('2025-06-26', 300.00), ('2025-06-23', 450.00), ('2025-06-20', 300.00),
            ('2025-06-18', 300.00), ('2025-06-16', 450.00), ('2025-06-12', 150.00),
            ('2025-06-12', 300.00), ('2025-06-09', 450.00), ('2025-06-05', 300.00),
            ('2025-06-05', 150.00), ('2025-06-03', 450.00), ('2025-05-30', 150.00),
            ('2025-05-26', 450.00), ('2025-05-23', 450.00), ('2025-05-28', 300.00),
            ('2025-05-21', 300.00), ('2025-05-19', 450.00), ('2025-05-07', 300.00),
            ('2025-05-09', 300.00), ('2025-05-14', 300.00), ('2025-05-12', 450.00),
            ('2025-04-28', 300.00), ('2025-05-16', 150.00), ('2025-05-02', 300.00),
            ('2025-05-05', 450.00), ('2025-04-30', 150.00), ('2025-04-30', 300.00),
            ('2025-04-17', 150.00), ('2025-04-14', 450.00), ('2025-04-25', 300.00),
            ('2025-04-24', 450.00), ('2025-04-22', 450.00), ('2025-04-11', 150.00),
            ('2025-04-07', 150.00), ('2025-04-04', 450.00), ('2025-04-09', 300.00),
            ('2025-04-07', 300.00), ('2025-04-02', 300.00), ('2025-04-01', 450.00),
            ('2025-03-28', 150.00), ('2025-03-26', 300.00), ('2025-03-21', 150.00),
            ('2025-03-24', 450.00), ('2025-03-19', 300.00), ('2025-03-17', 450.00),
            ('2025-03-14', 150.00), ('2025-03-12', 300.00), ('2025-03-07', 150.00),
            ('2025-03-07', 150.00), ('2025-03-05', 300.00), ('2025-03-10', 450.00),
            ('2025-03-03', 450.00), ('2025-02-28', 150.00), ('2025-02-26', 300.00),
            ('2025-02-24', 450.00), ('2025-02-21', 150.00), ('2025-02-17', 150.00),
            ('2025-02-17', 300.00), ('2025-02-19', 450.00), ('2025-02-14', 150.00),
            ('2025-02-12', 450.00), ('2025-02-10', 450.00), ('2025-02-05', 450.00),
            ('2025-02-03', 450.00), ('2025-01-27', 450.00), ('2025-01-29', 450.00),
            ('2025-01-22', 450.00), ('2025-01-16', 300.00), ('2025-01-20', 450.00),
            ('2025-01-10', 300.00), ('2025-01-13', 450.00), ('2025-01-08', 300.00),
            ('2025-01-06', 450.00), ('2025-01-02', 300.00), ('2024-12-31', 450.00),
            ('2024-12-31', 150.00), ('2024-12-31', 300.00), ('2024-12-23', 450.00),
            ('2024-12-20', 300.00), ('2024-12-18', 300.00), ('2024-12-16', 450.00),
            ('2024-12-13', 300.00), ('2024-12-01', 450.00), ('2024-12-11', 300.00),
            ('2024-12-09', 450.00), ('2024-12-05', 450.00), ('2024-12-06', 300.00),
            ('2024-12-02', 450.01), ('2024-11-28', 300.00), ('2024-11-25', 450.00),
            ('2024-11-22', 300.00), ('2024-11-18', 450.00), ('2024-11-21', 600.00),
            ('2024-11-14', 450.01), ('2024-11-14', 300.00), ('2024-11-11', 450.01),
            ('2024-11-07', 300.00), ('2024-10-31', 450.00), ('2024-10-28', 450.01),
            ('2024-10-22', 450.00), ('2024-10-24', 300.00), ('2024-10-01', 450.00),
            ('2024-10-01', 60.00), ('2024-10-01', 450.00), ('2024-10-04', 150.00),
            ('2024-10-11', 450.00), ('2024-10-14', 450.00), ('2024-10-17', 450.00),
            ('2024-10-03', 300.00), ('2024-09-23', 450.00), ('2024-09-26', 300.00),
            ('2024-09-13', 150.00), ('2024-09-19', 300.00), ('2024-09-16', 450.00),
            ('2024-09-12', 300.00), ('2024-09-09', 450.01), ('2024-09-05', 300.00),
            ('2024-08-29', 450.00), ('2024-09-02', 450.00), ('2024-08-26', 450.00),
            ('2024-08-22', 300.00), ('2024-08-19', 450.00), ('2024-08-15', 300.00),
            ('2024-08-13', 450.00), ('2024-08-08', 300.00), ('2024-08-05', 450.00),
            ('2024-08-02', 150.00), ('2024-08-01', 300.00), ('2024-07-31', 150.00),
            ('2024-07-30', 300.00), ('2024-07-26', 150.00), ('2024-07-25', 300.00),
            ('2024-07-22', 450.00), ('2024-07-18', 300.00), ('2024-07-15', 450.00),
            ('2024-07-11', 300.00), ('2024-07-08', 450.00), ('2024-07-04', 300.00),
            ('2024-07-01', 450.00)
        ]

        historical_data_with_period = [
            (date, qty, '2024/2025') for date, qty in base_historical_data
        ]

        c.executemany('''INSERT INTO historical_orders (date, order_quantity, analysis_period)
                         VALUES (?, ?, ?)''', historical_data_with_period)

        conn.commit()

    # --- Part 2: Find and fix any old records that don't have a period tag ---
    c.execute("SELECT COUNT(*) FROM historical_orders WHERE analysis_period IS NULL")
    untagged_count = c.fetchone()[0]

    if untagged_count > 0:
        print(f"Found {untagged_count} untagged historical records. Updating them to the '2024/2025' period...")
        # This SQL command updates all rows where the 'analysis_period' column is empty
        c.execute("""
            UPDATE historical_orders
            SET analysis_period = '2024/2025'
            WHERE analysis_period IS NULL
        """)
        conn.commit()
        print("Database update complete.")

    conn.close()

def get_period_from_date(order_date):
    """
    Determines the correct financial period string (e.g., '2025/2026')
    based on a given date, assuming a fiscal year starts in July.

    Args:
        order_date (datetime.date or datetime.datetime): The date of the transaction.

    Returns:
        str: The corresponding analysis period string.
    """
    if order_date.month >= 7:
        # If it's July or later, the financial year starts in the current year.
        start_year = order_date.year
    else:
        # If it's June or earlier, the financial year started in the previous year.
        start_year = order_date.year - 1

    return f"{start_year}/{start_year + 1}"    


def get_historical_orders_from_db(period):
    """Retrieve historical orders from SQLite database for a specific analysis period"""
    conn = sqlite3.connect('dry_ice.db')
    c = conn.cursor()

    c.execute('''SELECT date, order_quantity, analysis_period FROM historical_orders
                 WHERE analysis_period = ? ORDER BY date''', (period,))
    orders = c.fetchall()

    conn.close()

    if orders:
        df = pd.DataFrame(orders, columns=['Date', 'Order_Quantity_kg', 'analysis_period'])

        # --- START OF THE NEW, IMPROVED FIX ---

        # 1. Keep a copy of the original date strings before we try to convert them.
        original_dates = df['Date'].copy()

        # 2. Convert the 'Date' column. Any date that can't be parsed will become 'NaT' (Not a Time).
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')

        # 3. Find the rows where the conversion failed (i.e., where 'Date' is now NaT).
        invalid_rows_mask = df['Date'].isnull()

        if invalid_rows_mask.any():
            # 4. Get the full details of the rows that had bad dates.
            # We use the mask to select the original bad date strings and other columns.
            bad_data_df = pd.DataFrame({
                'Problematic_Date_String': original_dates[invalid_rows_mask],
                'Order_Quantity_kg': df.loc[invalid_rows_mask, 'Order_Quantity_kg'],
                'Analysis_Period': df.loc[invalid_rows_mask, 'analysis_period']
            })

            # 5. Display a detailed, helpful warning to the user.
            st.warning(
                f"⚠️ Found and ignored {len(bad_data_df)} row(s) with an invalid date format. "
                "This can happen from a typo during manual data entry. Please review and fix these records in your database.",
                icon="❗"
            )
            # Use an expander to show the problematic data without cluttering the UI.
            with st.expander("Click here to see the problematic row(s)"):
                st.dataframe(bad_data_df, use_container_width=True)

            # 6. Finally, remove the bad rows from the main DataFrame so the rest of the app works.
            df.dropna(subset=['Date'], inplace=True)

        # --- END OF THE NEW, IMPROVED FIX ---

    else:
        df = pd.DataFrame(columns=['Date', 'Order_Quantity_kg', 'analysis_period'])

    return df

def add_transaction_to_history(transaction_type, quantity, description, date, period):
    """Add transaction to session state and to database for a specific period"""
    transaction = {
        'date': datetime.combine(date, datetime.min.time()) if isinstance(date, type(datetime.today().date())) else date,
        'type': transaction_type,
        'quantity': quantity,
        'item': 'Dry Ice',
        'description': description,
        'notes': f"{description} - {quantity} kg"
    }

    # Add to database with the specified period
    add_transaction_to_db(transaction_type, quantity, description, date, period)

    # Update session state
    if 'transactions' not in st.session_state:
        st.session_state.transactions = []

    st.session_state.transactions.append(transaction)



def create_ensemble_forecast(df, forecast_days=30):
    """
    Create ensemble forecast combining Prophet, LSTM, ARIMA and Monte Carlo.
    This version includes robust error handling and non-negative constraints.
    """
    # Import required libraries with error handling
    try:
        from sklearn.preprocessing import MinMaxScaler
        sklearn_available = True
    except ImportError:
        print("Warning: scikit-learn not available, LSTM forecast will be skipped")
        sklearn_available = False
    
    try:
        import torch
        import torch.nn as nn
        pytorch_available = True
    except ImportError:
        print("Warning: PyTorch not available, LSTM forecast will be skipped")
        pytorch_available = False

    try:
        from statsmodels.tsa.arima.model import ARIMA
        statsmodels_available = True
    except ImportError:
        print("Warning: statsmodels not available, ARIMA forecast will be skipped")
        statsmodels_available = False
        
    try:
        from prophet import Prophet
        prophet_available = True
    except ImportError:
        print("Warning: Prophet not available, it will be skipped")
        prophet_available = False

    # 1. Prepare data with validation
    dates = pd.to_datetime(df['Date'])
    values = df['Order_Quantity_kg'].values.astype(float)
    mape = 0.0

    # CRITICAL FIX: Data validation and fallback
    if len(values) == 0:
        st.warning("No historical data available for forecasting. Using default conservative estimates.")
        conservative_forecast = np.full(forecast_days, 300.0)  # Default 300kg/day
        return None, conservative_forecast, {'Conservative': 300.0}, 0.0
    
    if len(values) < 5:
        st.warning(f"⚠️ Limited historical data ({len(values)} points). Forecast reliability may be reduced.")
        # Use simple average for limited data
        avg_demand = np.mean(values) if len(values) > 0 else 300.0
        conservative_forecast = np.full(forecast_days, max(0, avg_demand))
        
        # Create a simple visualization
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=values, name='Actual Demand', 
                                line=dict(color='blue', width=2)))
        future_dates = pd.date_range(dates.max(), periods=forecast_days + 1)[1:]
        fig.add_trace(go.Scatter(x=future_dates, y=conservative_forecast, 
                                name='Conservative Forecast', 
                                line=dict(color='orange', width=3)))
        fig.update_layout(title='Conservative Forecast (Limited Historical Data)', 
                         xaxis_title='Date', yaxis_title='Demand (kg)')
        
        return fig, conservative_forecast, {'Conservative': avg_demand}, 0.0

    # Define the smart Prophet model configuration
    def get_prophet_model():
        model = Prophet(
            seasonality_mode='multiplicative',
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.8  # Adjust confidence intervals
        )
        model.add_country_holidays(country_name='KE')
        return model

    # --- A. Backtesting Section (to calculate MAPE) ---
    test_size = min(30, len(values) // 3)  # Use 1/3 of data for testing, max 30 points
    
    if prophet_available and len(values) > test_size * 2:
        try:
            # Split data into training and testing sets for backtesting
            train_df = df.iloc[:-test_size]
            test_df = df.iloc[-test_size:]

            # Rename for Prophet
            prophet_train_df = train_df.rename(columns={'Date': 'ds', 'Order_Quantity_kg': 'y'})

            # Train the smart model on the training data
            backtest_model = get_prophet_model()
            
            # Suppress Prophet warnings during fitting
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                backtest_model.fit(prophet_train_df)

            # Create a future dataframe for the test period
            future_backtest = backtest_model.make_future_dataframe(periods=test_size)
            
            # Generate the forecast for the test period
            backtest_forecast_df = backtest_model.predict(future_backtest)
            
            # Extract the forecasted values that correspond to the test period
            backtest_predictions = backtest_forecast_df['yhat'].values[-test_size:]
            
            # CRITICAL FIX: Ensure non-negative predictions
            backtest_predictions = np.maximum(backtest_predictions, 0)
            
            # Get the actual values from the test set
            test_actuals = test_df['Order_Quantity_kg'].values

            # Filter out days where actual sales were zero to avoid division-by-zero errors
            non_zero_mask = test_actuals > 0
            test_actuals_safe = test_actuals[non_zero_mask]
            backtest_predictions_safe = backtest_predictions[non_zero_mask]

            # Calculate MAPE only on the non-zero days
            if len(test_actuals_safe) > 0:
                mape = mean_absolute_percentage_error(test_actuals_safe, backtest_predictions_safe)
            else:
                mape = 0.0

        except Exception as e:
            print(f"Prophet backtesting failed: {e}. Using default accuracy.")
            mape = 0.2  # Default 20% error rate
    
    # --- B. Main Forecasting Section (for the chart) ---
    
    # 2. Prophet forecast (on full dataset)
    if prophet_available and len(values) >= 2:
        try:
            prophet_df = df.rename(columns={'Date': 'ds', 'Order_Quantity_kg': 'y'})
            main_model = get_prophet_model()
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                main_model.fit(prophet_df)
                
            future = main_model.make_future_dataframe(periods=forecast_days)
            prophet_forecast_df = main_model.predict(future)
            prophet_values = prophet_forecast_df['yhat'].values[-forecast_days:]
            
            # CRITICAL FIX: Ensure non-negative values
            prophet_values = np.maximum(prophet_values, 0)
            
        except Exception as e:
            print(f"Prophet forecast failed: {e}. Using fallback.")
            prophet_values = np.full(forecast_days, max(0, np.mean(values)))
    else:
        prophet_values = np.full(forecast_days, max(0, np.mean(values)) if len(values) > 0 else 0)

    # 3. ARIMA forecast (on full dataset)
    if statsmodels_available and len(values) > 10:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                arima_model = ARIMA(values, order=(2,1,1))  # Simpler model
                arima_fit = arima_model.fit()
                arima_forecast = arima_fit.forecast(steps=forecast_days)
                
            # CRITICAL FIX: Ensure non-negative values
            arima_forecast = np.maximum(arima_forecast, 0)
            
        except Exception as e:
            print(f"ARIMA forecast failed: {e}. Using average.")
            arima_forecast = np.full(forecast_days, max(0, np.mean(values)))
    else:
        arima_forecast = np.full(forecast_days, max(0, np.mean(values)) if len(values) > 0 else 0)

    # 4. LSTM forecast (simplified for stability)
    lstm_forecast = np.full(forecast_days, max(0, np.mean(values)) if len(values) > 0 else 0)

    # 5. Monte Carlo forecast
    def discrete_event_monte_carlo(df_mc, n_simulations=1000, days_to_forecast=30):
        df_mc = df_mc[df_mc['Order_Quantity_kg'] > 0].sort_values('Date').reset_index(drop=True)
        if len(df_mc) < 2: 
            return np.full(days_to_forecast, max(0, np.mean(values)) if len(values) > 0 else 0)
            
        inter_arrival_times = df_mc['Date'].diff().dt.days.dropna()
        if len(inter_arrival_times) < 2:
            return np.full(days_to_forecast, max(0, np.mean(values)) if len(values) > 0 else 0)

        mean_time, std_time = inter_arrival_times.mean(), inter_arrival_times.std()
        mean_size, std_size = df_mc['Order_Quantity_kg'].mean(), df_mc['Order_Quantity_kg'].std()

        # Add safety checks
        if pd.isna(std_time) or std_time <= 0:
            std_time = max(1, mean_time * 0.1)
        if pd.isna(std_size) or std_size <= 0:
            std_size = max(1, mean_size * 0.1)

        all_simulations = []
        for _ in range(n_simulations):
            daily_demand = [0] * days_to_forecast
            current_day = 0
            while current_day < days_to_forecast:
                time_to_next_raw = np.random.normal(mean_time, std_time)
                time_to_next = max(1, round(time_to_next_raw))
                order_day = current_day + int(time_to_next)

                if order_day < days_to_forecast:
                    order_quantity_raw = np.random.normal(mean_size, std_size)
                    order_quantity = max(0, order_quantity_raw)  # Ensure non-negative
                    daily_demand[order_day] += order_quantity
                current_day = order_day
            all_simulations.append(daily_demand)
        
        mc_result = np.median(all_simulations, axis=0)
        return np.maximum(mc_result, 0)  # Final safety check

    mc_forecast = discrete_event_monte_carlo(df, days_to_forecast=forecast_days)

    # 6. Create weighted ensemble with non-negative constraint
    models = [prophet_values, arima_forecast, lstm_forecast, mc_forecast]
    weights = [0.5, 0.2, 0.15, 0.15]  # Prophet gets 50%
    ensemble_forecast = np.average(models, axis=0, weights=weights)
    
    # CRITICAL FIX: Final non-negative constraint
    ensemble_forecast = np.maximum(ensemble_forecast, 0)

    # 7. Create visualization
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, name='Actual Demand', 
                            line=dict(color='blue', width=2)))
    future_dates = pd.date_range(dates.max(), periods=forecast_days + 1)[1:]
    
    # Add individual model traces
    fig.add_trace(go.Scatter(x=future_dates, y=prophet_values, name='Prophet', 
                            line=dict(dash='dot', color='green')))
    fig.add_trace(go.Scatter(x=future_dates, y=arima_forecast, name='ARIMA', 
                            line=dict(dash='dot', color='red')))
    fig.add_trace(go.Scatter(x=future_dates, y=lstm_forecast, name='LSTM', 
                            line=dict(dash='dot', color='purple')))
    fig.add_trace(go.Scatter(x=future_dates, y=mc_forecast, name='Monte Carlo', 
                            line=dict(dash='dot', color='orange')))
    fig.add_trace(go.Scatter(x=future_dates, y=ensemble_forecast, name='Ensemble Forecast', 
                            line=dict(color='black', width=3)))
    
    fig.update_layout(
        title='30-Day Demand Forecast with Ensemble Methods', 
        xaxis_title='Date', 
        yaxis_title='Demand (kg)', 
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    model_forecasts = {
        'Prophet': np.mean(prophet_values),
        'ARIMA': np.mean(arima_forecast),
        'LSTM': np.mean(lstm_forecast),
        'Monte Carlo': np.mean(mc_forecast)
    }

    return fig, ensemble_forecast, model_forecasts, mape

def create_enhanced_charts(df, analyzer, kpis, forecast_data, safety_stock):
    """Create enhanced visualizations with all required parameters"""
    # 1. Order Pattern Analysis
    fig_orders = make_subplots(
        rows=2, cols=1,
        subplot_titles=("Order Quantities Over Time", "Order Size Distribution"),
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # Time series
    fig_orders.add_trace(
        go.Scatter(x=df['Date'], y=df['Order_Quantity_kg'],
                  mode='markers+lines', name='Order Quantity',
                  line=dict(color='#1f77b4')), row=1, col=1
    )

    # Distribution
    fig_orders.add_trace(
        go.Histogram(x=df['Order_Quantity_kg'], name='Order Size Distribution',
                    nbinsx=20, opacity=0.7), row=2, col=1
    )

    fig_orders.update_layout(height=600, showlegend=True)

    # 2. Cost Analysis Chart - Calculate costs if columns don't exist
    if 'Transport_Cost' not in df.columns:
        df['Transport_Cost'] = constants.TRANSPORT_COST  # Assuming fixed cost per order

    if 'Total_Cost' not in df.columns:
        df['Total_Cost'] = df['Order_Quantity_kg'] * constants.PRICE_PER_KG

    cost_data = pd.DataFrame({
        'Date': df['Date'],
        'Transport_Cost': df['Transport_Cost'],
        'Product_Cost': df['Total_Cost'],
        'Total_Cost': df['Transport_Cost'] + df['Total_Cost']
    })

    fig_cost = px.area(cost_data, x='Date', y=['Transport_Cost', 'Product_Cost'],
                      title="Cost Breakdown Over Time",
                      color_discrete_map={
                          'Transport_Cost': '#ff6b6b',
                          'Product_Cost': '#4ecdc4'
                      })

    # 3. Forecast Chart
    fig_forecast = None
    if forecast_data is not None:
        fig_forecast = go.Figure()

        # Historical data
        fig_forecast.add_trace(go.Scatter(
            x=df['Date'], y=df['Order_Quantity_kg'],
            mode='markers+lines', name='Historical Orders',
            line=dict(color='#1f77b4')
        ))

        # Forecast
        future_data = forecast_data[forecast_data['ds'] > df['Date'].max()]
        fig_forecast.add_trace(go.Scatter(
            x=future_data['ds'], y=future_data['yhat'],
            mode='lines', name='Forecast',
            line=dict(color='#ff7f0e')
        ))

        # Confidence intervals
        fig_forecast.add_trace(go.Scatter(
            x=future_data['ds'], y=future_data['yhat_upper'],
            fill=None, mode='lines', line_color='rgba(0,0,0,0)',
            showlegend=False
        ))
        fig_forecast.add_trace(go.Scatter(
            x=future_data['ds'], y=future_data['yhat_lower'],
            fill='tonexty', mode='lines', line_color='rgba(0,0,0,0)',
            name='Confidence Interval', fillcolor='rgba(255,127,14,0.3)'
        ))

        # Safety stock line
        fig_forecast.add_hline(y=safety_stock, line_dash="dot",
                              annotation_text=f"Safety Stock: {safety_stock:.1f} kg",
                              line_color="red")

        fig_forecast.update_layout(title="Demand Forecast (30 Days)")

    return fig_orders, fig_cost, fig_forecast

def main():
    # Initialize database
    init_db()
    seed_historical_data()

    st.sidebar.header("🗓️ Analysis Period")
    analysis_periods = ['2024/2025', '2025/2026', '2026/2027', '2027/2028']

    if 'selected_period' not in st.session_state:
        st.session_state.selected_period = '2024/2025'

    selected_period = st.sidebar.selectbox(
        "Choose a period to analyze or update:",
        analysis_periods,
        index=analysis_periods.index(st.session_state.selected_period)
    )
    st.session_state.selected_period = selected_period

    # Get today's date once
    today = datetime.today()
    try:
        start_year = int(selected_period.split('/')[0])
    except (ValueError, IndexError):
        st.error("Invalid analysis period format. Using current year as fallback.")
        start_year = today.year

    # 1. Parse the start year from the selected period string (e.g., '2025/2026' -> 2025)
    try:
        start_year = int(selected_period.split('/')[0])
    except (ValueError, IndexError):
        st.error("Invalid analysis period format. Check the 'analysis_periods' list.")
        st.stop()

    # 2. Define the fixed start date and the potential (full year) end date
    display_start_date = datetime(start_year, 7, 1)
    display_end_date = datetime(start_year + 1, 6, 30)

    # 3. Determine the final end_date using your logic: the earlier of the potential end date or today
    # --- SET 2: DATES FOR FILTERING THE DATA (Cannot go past today) ---
    filter_start_date = display_start_date
    filter_end_date = min(display_end_date, today) # The end date for analysis is the earlier of the two

    alert = None
    # Initialize components

    # THIS LINE IS MODIFIED to use the selected period from the dropdown
    df = get_historical_orders_from_db(st.session_state.selected_period)

    # ADD THIS BLOCK to handle cases where a new period has no data yet
    if df.empty:
        st.info(f"No order data found for the {st.session_state.selected_period} period. Record a receipt in the sidebar to begin the analysis.")
        # Create an empty df with correct columns to prevent errors downstream
        df = pd.DataFrame(columns=['Date', 'Order_Quantity_kg', 'Containers_Used', 'Transport_Cost', 'Total_Cost'])

    # The rest of your analysis code will now work on the period-specific 'df'
    analyzer = DryIceAnalyzer(df)
    kpis = analyzer.calculate_kpis(period=st.session_state.selected_period)

    # Initialize other components
    mobile_ui = MobileInterface()
    #alerts_system = SmartAlerts(inventory_tracker)
    maintenance_system = PredictiveMaintenance()
    integration_system = SystemIntegrations()

    # Initialize session state for transactions
    if 'last_loaded_period' not in st.session_state or st.session_state.last_loaded_period != st.session_state.selected_period:
        print(f"Period changed. Loading transactions for {st.session_state.selected_period}...")
        st.session_state.transactions = get_transactions_from_db(st.session_state.selected_period)
        st.session_state.last_loaded_period = st.session_state.selected_period # Update the tracker
    
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .alert-critical {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 10px;
        margin: 10px 0;
    }
    .alert-warning {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 10px;
        margin: 10px 0;
    }
    [data-testid="stMetricValue"] {
        font-size: 20px; /* Adjust this value as needed */
    }
    </style>
    """, unsafe_allow_html=True)

    # --- 1. Generate Forecast (Logic from former Tab 2) ---
    if not df.empty:
        daily_df = df.set_index('Date').resample('D')['Order_Quantity_kg'].sum().reset_index()
        daily_df = daily_df.rename(columns={'Date': 'Date', 'Order_Quantity_kg': 'Order_Quantity_kg'})
        fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy = create_ensemble_forecast(daily_df, forecast_days=30)
        total_forecasted_demand = np.sum(ensemble_forecast_values)
        forecast_std_dev = np.std(ensemble_forecast_values)
    else:
        # Provide default values if no data exists
        fig_ensemble, ensemble_forecast_values, model_forecasts, backtest_accuracy = None, np.array([0]), {}, 0
        total_forecasted_demand = 0
        forecast_std_dev = 0

    if total_forecasted_demand <= 0:
        st.warning("⚠️ Forecast resulted in zero/negative demand. Using intelligent fallback.")
        # Use historical KPIs as fallback
        fallback_monthly_demand = max(
            kpis.get('current_monthly_volume', 0),
            kpis.get('avg_order_size', 300) * 4,  # Assume 4 orders per month minimum
            1200  # Absolute minimum of 1200kg/month
        )
        total_forecasted_demand = fallback_monthly_demand
        forecast_std_dev = total_forecasted_demand * 0.25  # 25% coefficient of variation
        st.info(f"Using fallback monthly demand: {total_forecasted_demand:,.0f} kg")

    # --- 2. Calculate Inventory Policy (Logic from former Tab 3) ---
    # Use forecast demand if available, otherwise fallback to historical KPIs
    monthly_demand_input = total_forecasted_demand if total_forecasted_demand > 0 else kpis.get('current_monthly_volume', 0)
    demand_stddev_input = forecast_std_dev * np.sqrt(30) if forecast_std_dev > 0 else kpis.get('std_order_size', 0) * math.sqrt(4) #Approx 4 weeks in month

    # Calculate policy parameters
    avg_sublimation = sum(constants.SUB_LOSS_RANGE) / 2 / 100
    sublimation_factor = 1 + avg_sublimation
    adjusted_demand = monthly_demand_input * sublimation_factor
    
    z_score = stats.norm.ppf(constants.SERVICE_LEVEL)
    eoq = math.sqrt((2 * adjusted_demand * constants.TRANSPORT_COST) / (constants.HOLDING_RATE * constants.PRICE_PER_KG)) if (constants.HOLDING_RATE * constants.PRICE_PER_KG) > 0 else 0
    safety_stock = z_score * demand_stddev_input * math.sqrt(constants.LEAD_TIME_DAYS) * sublimation_factor
    reorder_point = (adjusted_demand / 30 * constants.LEAD_TIME_DAYS) + safety_stock

    # --- 3. Calculate the Definitive Annual Transport Savings ---
    current_monthly_orders = kpis.get('order_frequency', 0)
    eoq_monthly_orders = adjusted_demand / eoq if eoq > 0 else 0
    annual_transport_savings = (current_monthly_orders - eoq_monthly_orders) * 12 * constants.TRANSPORT_COST

    # Ensure savings cannot be negative
    annual_transport_savings = max(0, annual_transport_savings)

    # --- 4. Recalculate Total Annual Spending & Other Costs ---
    annual_volume = kpis.get('total_volume', 0)
    annual_product_cost = annual_volume * constants.PRICE_PER_KG
    annual_transport_cost = kpis.get('total_orders', 0) * constants.TRANSPORT_COST
    annual_sublimation_loss = annual_volume * constants.PRICE_PER_KG * avg_sublimation

    # Corrected holding cost calculation
    average_inventory_level = (kpis.get('avg_order_size', 0) / 2) + safety_stock
    annual_holding_cost = average_inventory_level * constants.PRICE_PER_KG * constants.HOLDING_RATE
    
    total_annual_spending = annual_product_cost + annual_transport_cost + annual_holding_cost + annual_sublimation_loss

    # --- 5. Generate Other Charts and Visualizations ---
    # The original Prophet forecast_data object for chart in Tab 1
    forecast_data = analyzer.forecast_demand()
    fig_orders, fig_cost, fig_forecast = create_enhanced_charts(
        df=df, analyzer=analyzer, kpis=kpis, forecast_data=forecast_data, safety_stock=safety_stock
    )
    
    # Get current stock from the database
    current_stock = get_current_stock_from_db()

    # If the database is empty, seed it with the smart, dynamically calculated value
    if current_stock == 0:
        target_days_coverage = 45
        # average_daily_demand is now calculated based on forecast values if available
        avg_daily_forecast = np.mean(ensemble_forecast_values) if total_forecasted_demand > 0 else (kpis.get('avg_order_size', 0) / 7)

        # Use the final, forecast-driven eoq and safety_stock values
        initial_stock = max(
            eoq * 2,                                    # Ensure at least 2 order cycles
            safety_stock * 4,                           # Ensure adequate safety buffer
            avg_daily_forecast * target_days_coverage   # Meet strategic coverage goals
        )
        # Ensure initial stock is not zero if all calculations result in zero (e.g., no data)
        if initial_stock <= 0:
            initial_stock = 1000 # Fallback to a default value

        current_stock = initial_stock
        update_current_stock_in_db(current_stock, datetime.now())
        print(f"Database was empty. Seeded initial stock with: {current_stock:.2f} kg")

    # Initialize the inventory tracker with the definitive current_stock value
    inventory_tracker = InventoryTracker(
        initial_stock=current_stock,
        analyzer=analyzer
    )
   
    # Initialize SmartAlerts after inventory_tracker is created
    alerts_system = SmartAlerts(inventory_tracker)
    mobile_ui.optimize_for_mobile()

    # Header
    start_date_str = display_start_date.strftime('%B %d, %Y') # e.g., July 01, 2025
    end_date_str = display_end_date.strftime('%B %d, %Y')   # e.g., June 30, 2026

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        try:
            st.image("assets/browns_logo.png", width=150)
        except:
            # Fallback if logo file not found
            st.markdown("""
            <div style="text-align: center;">
                <div style="font-size: 4rem;">❄️</div>
                <h1 style="color: #2E5266; margin: 0;">Brown's Food Co.</h1>
                <h3 style="color: #6B9AB8; margin: 0;">DRY ICE INVENTORY OPTIMIZER</h3>
            </div>
            """, unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center;font-size:1.2rem;margin-bottom:2rem;">Analysis Period: {start_date_str} to {end_date_str}</div>',
                unsafe_allow_html=True)

    st.sidebar.header("📦 Real-time Inventory")

    current_stock_input = st.sidebar.number_input(
        "Current Stock (kg)",
        min_value=0.0,
        value=float(inventory_tracker.current_stock),
        step=50.0,
        help="Enter the current stock level in kilograms"
    )

    # Update tracker only if value changed
    if current_stock_input != inventory_tracker.current_stock:
        inventory_tracker.current_stock = current_stock_input
        update_current_stock_in_db(current_stock_input, datetime.now())

    # Display status (LOW/CRITICAL/OK)
    status = inventory_tracker.get_stock_status()
    st.sidebar.markdown(
        f"**Status:** <span style='color:{status['color']};font-weight:bold'>"
        f"{status['status']}</span>",
        unsafe_allow_html=True
    )
    st.sidebar.subheader("Update Inventory")

    # Record Usage
    usage_date = st.sidebar.date_input("Usage Date", value=datetime.today())
    usage = st.sidebar.number_input("Quantity Used (kg)", min_value=0, value=150, step=10)

    if st.sidebar.button("Record Usage"):
        alert = inventory_tracker.update_stock(usage, "Daily Consumption", usage_date) or None
        add_transaction_to_history("usage", usage, "Daily Consumption", usage_date, st.session_state.selected_period)
        if alert is not None:
            st.sidebar.error(alert["message"])
        else:
            st.sidebar.success(f"Usage of {usage} kg recorded on {usage_date.strftime('%Y-%m-%d')}.")
        st.rerun()

    # Record Receipt
    receipt_date = st.sidebar.date_input("Receipt Date", value=datetime.today(), key="receipt_date")
    new_stock = st.sidebar.number_input("New Stock Received (kg)", min_value=0, value=0, step=50)

    if st.sidebar.button("Record Receipt"):
        
        correct_period = get_period_from_date(receipt_date)

        inventory_tracker.current_stock += new_stock
        update_current_stock_in_db(inventory_tracker.current_stock, receipt_date)
        add_transaction_to_history(
            transaction_type="receipt",
            quantity=new_stock,
            description="Stock Receipt",
            date=receipt_date,
            period=correct_period  # Use the derived period, not the one from the sidebar
        )

        # 3. Provide clear feedback to the user about what happened.
        st.sidebar.success(
            f"Order for {new_stock} kg on {receipt_date.strftime('%Y-%m-%d')} recorded. "
            f"It has been automatically assigned to the {correct_period} period."
        )

        # 4. (Optional but highly recommended UX improvement)
        # If the order belongs to a different period, switch the dashboard view to that period.
        if st.session_state.selected_period != correct_period:
            st.session_state.selected_period = correct_period
            st.sidebar.info(f"Dashboard view switched to {correct_period} to show your new entry.")

        # 5. Rerun the app to reflect all changes immediately.
        st.rerun()

    # Enhanced Stock Status Display
    stock_status = inventory_tracker.get_stock_status()
    st.sidebar.markdown(
        f"**Status:** <span style='color:{stock_status['color']};font-weight:bold'>"
        f"{stock_status['status']}</span>",
        unsafe_allow_html=True
    )

    max_stock = eoq + safety_stock * 2
    current_stock_val = inventory_tracker.current_stock
    progress_value = min(1.0, current_stock_val / max_stock) if max_stock > 0 else 0
    st.sidebar.progress(progress_value)
    st.sidebar.caption(f"Stock Level: {current_stock_val:.1f}/{max_stock:.1f} kg ({progress_value:.1%})")

    if stock_status['status'] in ['Low Stock', 'Critical']:
        st.sidebar.warning(f"⚠️ Consider reordering. Recommended order: {eoq:.1f} kg")    

    # Sidebar - Report Generator (Always Visible)
    st.sidebar.header("📄 Report Generation")
    if st.sidebar.button("Generate PDF Report", type="primary"):
        with st.spinner("Generating comprehensive report..."):
            try:
                if df is None or df.empty:
                    st.sidebar.error("No data available. Please upload data first.")
                else:
                    report = ReportGenerator(analyzer=analyzer, df=df)
                    report_path = report.generate_pdf()

                    with open(report_path, "rb") as f:
                        st.sidebar.download_button(
                            label="📥 Download Report",
                            data=f,
                            file_name=f"dry_ice_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                        )
                    st.sidebar.success("Report generated successfully!")
            except Exception as e:
                st.sidebar.error(f"Error generating report: {str(e)}")

    # Sidebar - System Parameters (Always Visible)
    st.sidebar.header("⚙️ System Parameters")
    with st.sidebar.expander("Inventory Parameters"):
        st.write(f"**Price per kg:** KSh {constants.PRICE_PER_KG:.2f}")
        st.write(f"**Container size:** {constants.CONTAINER_SIZE} kg")
        st.write(f"**Transport cost:** KSh {constants.TRANSPORT_COST:,.2f}")
        st.write(f"**Holding rate:** {constants.HOLDING_RATE*100:.1f}%")
        st.write(f"**Sublimation loss:** {constants.SUB_LOSS_RANGE[0]:.1f}-{constants.SUB_LOSS_RANGE[1]:.1f}%")
        st.write(f"**Lead time:** {constants.LEAD_TIME_DAYS} day(s)")
        st.write(f"**Service level:** {constants.SERVICE_LEVEL*100:.0f}%")

    # Sidebar - Data Summary (Always Visible)
    st.sidebar.header("📊 Data Summary")
    sidebar_start_str = display_start_date.strftime('%d/%m/%Y')
    sidebar_end_str = display_end_date.strftime('%d/%m/%Y')

    st.sidebar.write(f"**Analysis Period:** {sidebar_start_str} to {sidebar_end_str}")
    st.sidebar.write(f"**Total Orders:** {len(df):,}", help="Total number of orders processed")
    st.sidebar.write(f"**Data Points:** {df.shape[0]:,}", help="Total individual data records collected")

    # Sidebar - Footer (Always Visible)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Browns Cheese** 🧀")
    st.sidebar.markdown("Dry Ice Management System")
    st.sidebar.markdown("© 2025 - Gathura Chege")    

    # Updated KPI Dashboard (8 columns)
    st.markdown("### 📈 Key Performance Indicators")

    # --- ROW 1 ---
    cols1 = st.columns(4)
    with cols1[0]:
        st.metric("Total Orders", f"{kpis.get('total_orders', 0):,}")
    with cols1[1]:
        st.metric("Total Volume", f"{kpis.get('total_volume', 0):,.0f} kg")
    with cols1[2]:
        st.metric("Annual Spending", f"KSh {total_annual_spending:,.0f}")
    with cols1[3]:
        # THIS METRIC IS NOW CONSISTENT
        st.metric("Annual Transport Savings", f"KSh {annual_transport_savings:,.0f}")

    # --- ROW 2 ---
    cols2 = st.columns(4)
    with cols2[0]:
        st.metric("Safety Stock", f"{safety_stock:,.1f} kg")
    with cols2[1]:
        st.metric("Economic EOQ", f"{eoq:,.1f} kg")
    with cols2[2]:
        st.metric("Container Efficiency", f"{kpis.get('container_utilization', 0.0)*100:.1f}%")
    with cols2[3]:
        monthly_savings = annual_transport_savings / 12
        monthly_transport_cost = (current_monthly_orders * constants.TRANSPORT_COST)
        percent_savings = (monthly_savings / monthly_transport_cost) * 100 if monthly_transport_cost > 0 else 0
        st.metric("Monthly Savings", f"KSh {monthly_savings:,.0f}", f"{percent_savings:+.1f}%")

    # Display Alerts
    alerts = alerts_system.check_conditions(
        current_demand=usage,
        avg_demand=kpis.get('avg_order_size', 0),
        std_demand=kpis.get('std_order_size', 0),
        current_cost=analyzer.constants['transport_cost'] * 1.15,
        avg_cost=analyzer.constants['transport_cost']
    )
    if alerts:
        st.markdown("### ⚠️ Active Alerts")
    for alert in alerts_system.get_active_alerts():
        alert_class = "alert-critical" if "CRITICAL" in alert['message'] else "alert-warning"
        st.markdown(
            f"<div class='{alert_class}'>{alert['timestamp'].strftime('%H:%M')} - {alert['message']}</div>",
            unsafe_allow_html=True
        )
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Order Analysis",
        "🔮 Demand Forecast",
        "📦 Inventory Management",
        "💰 Cost Optimization",
        "📋 Recommendations",
        "🛠️ Maintenance",
        "📜 Transaction History"
    ])

    with tab1:
        if not df.empty:
            st.markdown("""
            <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px;'>
            Order Pattern & Cost Analysis
            </h2>
            """, unsafe_allow_html=True)
            with st.expander("Visual Analysis", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(fig_orders, use_container_width=True)
                with col2:
                    st.plotly_chart(fig_cost, use_container_width=True)

            st.markdown("""
            <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-top: 30px;'>
            Order Statistics
            </h2>
            """, unsafe_allow_html=True)

            stat_cols = st.columns(4)
            metric_style = """<style>.stMetric {border-left: 3px solid #4e79a7;padding: 10px 15px;border-radius: 5px;background-color: #f9f9f9;}</style>"""
            st.markdown(metric_style, unsafe_allow_html=True)

            metrics = [
                ("Average Order", f"{kpis.get('avg_order_size', 0):.1f} kg", "Average order quantity"),
                ("Order Std Dev", f"{kpis.get('std_order_size', 0):.1f} kg", "Variability in order sizes"),
                ("Monthly Orders", f"{kpis.get('order_frequency', 0):.1f}", "Total orders per month"),
                ("Avg Cost/Order", f"KSh {kpis.get('avg_cost_per_order', 0):,.0f}", "Average cost per order")
            ]

            for i, (label, value, help_text) in enumerate(metrics):
                with stat_cols[i]:
                    st.metric(label, value, help=help_text)

            st.markdown("""
            <h2 style='border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-top: 30px;'>
            Additional Insights
            </h2>
            """, unsafe_allow_html=True)

            insights_cols = st.columns([1, 1, 1], gap="large")

            with insights_cols[0]:
                with st.container():
                    st.markdown("#### 📊 Order Pattern Analysis")
                    order_counts = df['Order_Quantity_kg'].value_counts().sort_index()
                    most_common_order = order_counts.idxmax()
                    st.metric("Most common order size", f"{most_common_order:.0f} kg", f"{order_counts.max()} orders")

                    df['Weekday'] = df['Date'].dt.day_name()
                    weekday_pattern = df.groupby('Weekday')['Order_Quantity_kg'].count().sort_values(ascending=False)
                    st.metric("Busiest day", weekday_pattern.index[0], f"{weekday_pattern.iloc[0]} orders")

            with insights_cols[1]:
                with st.container():
                    st.markdown("#### ⚙️ Efficiency Metrics")
                    avg_containers_per_order = df['Containers_Used'].mean()
                    container_efficiency = (df['Order_Quantity_kg'].sum() / (df['Containers_Used'].sum() * constants.CONTAINER_SIZE)) * 100
                    st.metric("Avg containers per order", f"{avg_containers_per_order:.1f}")
                    st.metric("Container fill rate", f"{container_efficiency:.1f}%")

                    product_cost = constants.PRICE_PER_KG
                    transport_cost = (kpis.get('order_frequency', 0) * constants.TRANSPORT_COST) / kpis.get('current_monthly_volume', 1)
                    holding_cost = (kpis.get('avg_order_size', 0)/2) * constants.HOLDING_RATE * constants.PRICE_PER_KG / kpis.get('current_monthly_volume', 1)
                    
                    avg_sublimation_rate = sum(constants.SUB_LOSS_RANGE) / 2 / 100
                    sublimation_cost_per_kg = constants.PRICE_PER_KG * avg_sublimation_rate
                    
                    current_cost_per_kg = product_cost + transport_cost + holding_cost + sublimation_cost_per_kg
                    st.metric("Current cost per kg", f"KSh {current_cost_per_kg:.2f}", delta=None)

            with insights_cols[2]:
                with st.container():
                    st.markdown("#### 📈 Optimization Impact")
                    if eoq > 0:
                        order_frequency_reduction = ((kpis.get('order_frequency', 0) - (kpis.get('current_monthly_volume', 0) / eoq)) / kpis.get('order_frequency', 1) * 100)
                        st.metric("Order frequency reduction", f"{order_frequency_reduction:.1f}%")

                        current_turns = kpis.get('current_monthly_volume', 0) / (kpis.get('avg_order_size', 1)/2)
                        eoq_turns = 1.3
                        inventory_turns_improvement = eoq_turns - current_turns
                        st.metric("Inventory Turns Change", f"{inventory_turns_improvement:+.1f}x")

                    annual_savings = monthly_savings * 12
                    implementation_cost = 5000
                    roi = (annual_savings / implementation_cost) * 100 if implementation_cost > 0 else float('inf')
                    st.metric("Estimated ROI", f"{roi:.0f}%", help="Return on investment from implementing optimizations")
        else:
            st.warning("📊 No order data exists for this analysis period.")
            st.info("Use the 'Record Receipt' button in the sidebar to add the first order for this period.")

    with tab2:
        if not df.empty:
            st.markdown("### 🔮 30-Day Demand Forecast")

            # The forecast figure is now generated in the main block. We just display it here.
            if not fig_ensemble:
                st.warning("Unable to generate forecast. Please check data quality or model configurations.")
            else:
                st.plotly_chart(fig_ensemble, use_container_width=True)

            # --- Core Forecast Metrics ---
            adjusted_total_demand = total_forecasted_demand * sublimation_factor
            avg_daily_forecast = np.mean(ensemble_forecast_values)

            st.markdown("#### 📈 Forecast Summary (Next 30 Days)")
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric(
                    label="Total Forecasted Demand",
                    value=f"{total_forecasted_demand:,.0f} kg",
                    help="The total expected demand based on the ensemble model."
                )
            with summary_cols[1]:
                st.metric(
                    label="Required Purchase Volume",
                    value=f"{adjusted_total_demand:,.0f} kg",
                    delta=f"+{total_forecasted_demand * avg_sublimation:,.0f} kg",
                    help=f"The volume you need to buy to compensate for a {avg_sublimation:.1%} sublimation loss."
                )
            with summary_cols[2]:
                st.metric(
                    label="Average Daily Demand",
                    value=f"{avg_daily_forecast:,.1f} kg/day",
                    help="The average demand expected per day over the next 30 days."
                )
            with summary_cols[3]:
                st.metric(
                    label="Forecast Accuracy",
                    value=f"{100-backtest_accuracy*100:.1f}%",
                    help="Model accuracy (1-MAPE) based on backtesting on historical data."
                )

            # --- Probabilistic Forecast for Risk Management ---
            st.markdown("#### 📊 Risk-Based Demand Scenarios")
            st.markdown("Instead of a single number, it's better to plan for a range of possibilities. This shows a likely scenario versus a high-demand (worst-case) scenario.")

            p50_total_demand = total_forecasted_demand
            p90_total_demand = total_forecasted_demand + (1.282 * forecast_std_dev * np.sqrt(30))

            risk_cols = st.columns(2)
            with risk_cols[0]:
                st.info("##### Likely Scenario (50th Percentile)")
                st.metric(
                    label="Likely Monthly Demand",
                    value=f"~{p50_total_demand:,.0f} kg"
                )
                st.write("There is a 50% chance demand will be at or below this level.")
            with risk_cols[1]:
                st.warning("##### High-Demand Scenario (90th Percentile)")
                st.metric(
                    label="Worst-Case Monthly Demand",
                    value=f"~{p90_total_demand:,.0f} kg"
                )
                st.write("There is a 10% chance demand will exceed this level. Use this for setting safety stock and risk buffers.")

            # --- Individual Model Breakdown ---
            with st.expander("🔬 View Individual Model Performance"):
                st.markdown("The final forecast is a weighted average of these underlying models.")
                model_cols = st.columns(len(model_forecasts))
                for i, (model_name, daily_avg) in enumerate(model_forecasts.items()):
                    with model_cols[i]:
                        st.metric(
                            label=model_name,
                            value=f"{daily_avg:.1f} kg/day",
                            help=f"The average daily forecast from the {model_name} model."
                        )
        else:
            st.warning("🔮 Cannot generate a forecast without historical data for this period.")
            st.info("Please record some receipts to build up an order history.")

    with tab3:
        if not df.empty:
            st.markdown("### 📦 Proactive Inventory Policy")
            st.success("✅ Inventory policy is dynamically calculated using the live forecast data from Tab 2.")
            
            st.markdown("### ❄️ Inventory Optimization Formulas")
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Economic Order Quantity (EOQ)")
                st.latex(r'\text{EOQ} = \sqrt{\frac{2 \times D \times S}{H \times C}}')
                st.latex(r'D_{\text{adj}} = %.1f \times %.4f = %.1f' % (monthly_demand_input, sublimation_factor, adjusted_demand))
                st.latex(r'\text{EOQ} = \sqrt{\frac{2 \times %.1f \times %.2f}{%.2f \times %.2f}} = %.1f \text{ kg}' % (adjusted_demand, constants.TRANSPORT_COST, constants.HOLDING_RATE, constants.PRICE_PER_KG, eoq))

                st.markdown("**Where:**")
                st.markdown(f"<span style='color:green;'>- D = Forecasted Monthly Demand = {monthly_demand_input:,.1f} kg</span>", unsafe_allow_html=True)
                st.write(f"- S = Ordering Cost = KSh {constants.TRANSPORT_COST:,.2f}")
                st.write(f"- H = Holding Rate = {constants.HOLDING_RATE*100:.1f}%")
                st.write(f"- C = Unit Cost = KSh {constants.PRICE_PER_KG:.2f}/kg")
                st.markdown(f"<p style='color:green; font-weight:bold;'>Result: EOQ = {eoq:.1f} kg</p>", unsafe_allow_html=True)

            with col2:
                st.markdown("#### Safety Stock")
                st.latex(r'\text{SS} = z \cdot \sigma_{\text{demand}} \cdot \sqrt{LT} \cdot (1 + \text{sublimation})')
                st.latex(r'= %.2f \times %.1f \times \sqrt{%d} \times %.4f = %.1f \text{ kg}' % (z_score, demand_stddev_input, constants.LEAD_TIME_DAYS, sublimation_factor, safety_stock))

                st.markdown("**Where:**")
                st.write(f"- z = Z-score ({constants.SERVICE_LEVEL*100:.0f}%) = {z_score:.2f}")
                st.markdown(f"<span style='color:green;'>- σ = Forecast Demand Std Dev = {demand_stddev_input:,.1f} kg</span>", unsafe_allow_html=True)
                st.write(f"- LT = Lead Time = {constants.LEAD_TIME_DAYS} days")
                st.write(f"- Sublimation Rate = {avg_sublimation:.2%}")
                st.markdown(f"<p style='color:green; font-weight:bold;'>Result: Safety Stock = {safety_stock:.1f} kg</p>", unsafe_allow_html=True)

            st.markdown("### 🔄 Reorder Point")
            st.markdown(f"**Reorder Point = ({adjusted_demand:.1f}/30 × {constants.LEAD_TIME_DAYS}) + {safety_stock:.1f} = {reorder_point:.1f} kg**")
            st.caption("*This policy is now dynamically updated based on the 30-day demand forecast.*")

            st.markdown("### 📊 Recommended Inventory Policy")
            policy_data = pd.DataFrame({'Metric': ['Economic Order Quantity', 'Safety Stock', 'Reorder Point', 'Maximum Inventory'], 'Value (kg)': [eoq, safety_stock, reorder_point, eoq + safety_stock]})
            st.dataframe(policy_data.style.format({'Value (kg)': '{:.1f}'}), use_container_width=True, )

            st.markdown("### 🎯 EOQ Implementation Impact")
            # The savings are now calculated in the main block. We just display them here.
            annual_savings_percentage = (annual_transport_savings / annual_transport_cost) * 100 if annual_transport_cost > 0 else 0

            impact_cols = st.columns(4)
            with impact_cols[0]:
                order_freq_delta_percent = ((eoq_monthly_orders - current_monthly_orders) / current_monthly_orders) * 100 if current_monthly_orders > 0 else 0
                st.metric("Order Frequency Change", f"{eoq_monthly_orders:.1f} orders/month", f"{order_freq_delta_percent:.1f}%")
            with impact_cols[1]:
                # THIS VALUE IS NOW CONSISTENT
                st.metric("Annual Transport Savings", f"KSh {annual_transport_savings:,.0f}", f"{annual_savings_percentage:.1f}% of total")

            implementation_cost = constants.IMPLEMENTATION_COST
            payback_period = implementation_cost / (annual_transport_savings / 12) if annual_transport_savings > 0 else 0
            roi_percentage = (annual_transport_savings / implementation_cost) * 100 if implementation_cost > 0 else 0
            with impact_cols[2]:
                st.metric("Payback Period", f"{payback_period:.1f} months")
            with impact_cols[3]:
                st.metric("Implementation ROI", f"{roi_percentage:.0f}%")

            st.markdown("### 🔄 Current vs. Forecast-Driven System Comparison")
            comparison_data = {
                'Metric': ['Orders per Month', 'Avg. Order Size (kg)', 'Monthly Transport Cost (KSh)', 'Annual Transport Cost (KSh)'],
                'Current System (Historical)': [
                    f"{current_monthly_orders:.1f}", f"{kpis.get('avg_order_size', 0):.0f}",
                    f"{current_monthly_orders * constants.TRANSPORT_COST:,.0f}", f"{annual_transport_cost:,.0f}"
                ],
                'EOQ System (Forecast-Driven)': [
                    f"{eoq_monthly_orders:.1f}", f"{eoq:.0f}",
                    f"{eoq_monthly_orders * constants.TRANSPORT_COST:,.0f}", f"{eoq_monthly_orders * 12 * constants.TRANSPORT_COST:,.0f}"
                ]
            }
            st.dataframe(pd.DataFrame(comparison_data), use_container_width=True, )

            st.markdown("#### 📈 5-Year Cumulative Savings Projection")
            years = list(range(1, 6))
            cumulative_savings = [annual_transport_savings * year for year in years]
            fig_savings = go.Figure()
            fig_savings.add_trace(go.Scatter(x=years, y=cumulative_savings, name="Cumulative Savings", line=dict(color='#3498db', width=3), mode='lines+markers'))
            fig_savings.add_hline(y=implementation_cost, line_dash="dot", annotation_text="Implementation Cost", line_color="red")
            fig_savings.update_layout(title="Projected Savings from Adopting Forecast-Driven EOQ", xaxis_title="Year", yaxis_title="Cumulative Savings (KSh)", height=400)
            st.plotly_chart(fig_savings, use_container_width=True)
        else:
            st.warning("📦 Cannot calculate inventory policy without historical data for this period.")
            st.info("Please record some receipts to build up an order history for inventory optimization.")

    with tab4:
        if not df.empty:
            st.markdown("### 🧮 Detailed Annual Cost Breakdown")
            
            # 1. Core Cost Components Table
            st.markdown("#### 📋 Annual Cost Component Details")
            avg_inventory_for_display = (kpis.get('avg_order_size', 0) / 2) + safety_stock
            cost_components_data = {
                'Component': ['Product Purchase', 'Transport', 'Holding', 'Sublimation Loss', 'Total'],
                'Calculation': [
                    f"{annual_volume:,.0f} kg × KSh {constants.PRICE_PER_KG:.2f}",
                    f"{kpis.get('total_orders', 0):,} orders × KSh {constants.TRANSPORT_COST:,.0f}",
                    f"({avg_inventory_for_display:,.1f} kg avg inv) × KSh {constants.PRICE_PER_KG:.2f} × {constants.HOLDING_RATE * 100:.1f}%",
                    f"{annual_volume:,.0f} kg × {sum(constants.SUB_LOSS_RANGE) / 2:.2f}% loss × KSh {constants.PRICE_PER_KG:.2f}",
                    "Sum of all components"
                ],
                'Annual Cost (KSh)': [
                    annual_product_cost, annual_transport_cost, annual_holding_cost,
                    annual_sublimation_loss, total_annual_spending
                ],
                '% of Total': [
                    (annual_product_cost / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    (annual_transport_cost / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    (annual_holding_cost / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    (annual_sublimation_loss / total_annual_spending) * 100 if total_annual_spending > 0 else 0,
                    100
                ]
            }
            cost_components = pd.DataFrame(cost_components_data)
            st.dataframe(cost_components.style.format({'Annual Cost (KSh)': '{:,.0f}', '% of Total': '{:.1f}%'}).applymap(lambda x: 'font-weight: bold', subset=['Component']).bar(subset=['Annual Cost (KSh)'], color='#5fba7d'), use_container_width=True)

            st.markdown("#### 📊 Cost Structure Visualization")
            fig = make_subplots(
                rows=1, cols=2,
                specs=[[{"type": "pie"}, {"type": "bar"}]],
                subplot_titles=("Cost Distribution", "Cost per kg Analysis"),
                column_widths=[0.5, 0.5]       
            )

            # Trace 1: Pie Chart with labels and percentages
            fig.add_trace(go.Pie(
                labels=cost_components['Component'][:-1],
                values=cost_components['Annual Cost (KSh)'][:-1],
                marker_colors=['#3498db','#e74c3c','#f39c12','#2ecc71'],
                textinfo='label+percent',  # Show both label and percentage
                textposition='inside',    # Place text inside slices
                insidetextorientation='radial',  # Curve the text
                textfont=dict(size=12),   # Adjust font size
                hoverinfo='label+percent+value',  # Show details on hover
                domain={'x': [0, 0.45]}
            ), row=1, col=1)

            # Trace 2: Bar Chart (Cost per kg)
            cost_per_kg_data = {
                'Metric': ['Product Cost', 'Transport Cost', 'Holding Cost', 'Sublimation'],
                'Cost per kg (KSh)': [
                    constants.PRICE_PER_KG,
                    annual_transport_cost / annual_volume if annual_volume > 0 else 0,
                    annual_holding_cost / annual_volume if annual_volume > 0 else 0,
                    annual_sublimation_loss / annual_volume if annual_volume > 0 else 0
                ]
            }
            cost_per_kg = pd.DataFrame(cost_per_kg_data)
            fig.add_trace(go.Bar(
                x=cost_per_kg['Metric'],
                y=cost_per_kg['Cost per kg (KSh)'],
                marker_color=['#3498db','#e74c3c','#f39c12','#2ecc71'],
                text=cost_per_kg['Cost per kg (KSh)'].round(2),
                textposition='auto'
            ), row=1, col=2)

            fig.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
           
            # 3. Monthly Charts
            st.markdown("#### 📈 Monthly Cost Trends (KSh)")
            
            df_monthly = df.copy()
            df_monthly['Date'] = pd.to_datetime(df_monthly['Date'])
            df_monthly['Month'] = df_monthly['Date'].dt.to_period('M').dt.strftime('%Y-%b')

            monthly_data = df_monthly.groupby('Month').agg(
                product_cost_ksh=('Total_Cost', 'sum'),
                transport_cost_ksh=('Transport_Cost', 'sum'),
                product_volume_kg=('Order_Quantity_kg', 'sum')
            ).reset_index()

            monthly_data['holding_cost_ksh'] = (monthly_data['product_volume_kg'] / 2) * constants.HOLDING_RATE * constants.PRICE_PER_KG
            monthly_data['sublimation_loss_ksh'] = monthly_data['product_volume_kg'] * avg_sublimation * constants.PRICE_PER_KG
            monthly_data['sublimation_loss_kg'] = monthly_data['product_volume_kg'] * avg_sublimation
            
            monthly_data['Month_dt'] = pd.to_datetime(monthly_data['Month'], format='%Y-%b')
            monthly_data = monthly_data.sort_values('Month_dt')
            
            cost_cols = ['product_cost_ksh', 'transport_cost_ksh', 'holding_cost_ksh', 'sublimation_loss_ksh']
            colors = ['#3498db', '#e74c3c', '#f39c12', '#2ecc71']
            color_map = {col: color for col, color in zip(cost_cols, colors)}

            fig_monthly_cost = px.area(
                monthly_data, x='Month', y=cost_cols,
                title="Monthly Cost Fluctuations (KSh)", labels={'value': 'Cost (KSh)', 'variable': 'Cost Type'},
                color_discrete_map=color_map
            )

            for col, color in zip(cost_cols, colors):
                avg_value = monthly_data[col].mean()
                annotation_label = col.replace('_ksh', '').replace('_', ' ').title()
                fig_monthly_cost.add_hline(y=avg_value, line_dash="dot", line_color=color,
                                        annotation_text=f"Avg {annotation_label}: {avg_value:,.0f}",
                                        annotation_position="bottom right")

            fig_monthly_cost.update_traces(
                mode="lines+markers",
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} KSh<extra></extra>"
            )
            fig_monthly_cost.update_layout(
                hovermode="x unified",
                xaxis_title=None,
                yaxis_title="Cost (KSh)",
                legend_title="Cost Type"
            )

            st.plotly_chart(fig_monthly_cost, use_container_width=True)

            st.markdown("#### 📊 Monthly Physical Quantities (kg)")
            fig_monthly_volume = px.bar(
                monthly_data, x='Month', y=['product_volume_kg', 'sublimation_loss_kg'],
                title="Monthly Dry Ice Quantities (kg)", labels={'value': 'Quantity (kg)', 'variable': 'Quantity Type'}
            )
            st.plotly_chart(fig_monthly_volume, use_container_width=True)

            # 4. Savings Summary (5-COLUMN LAYOUT)
            st.markdown("### 💰 Savings Summary")
            
            monthly_transport_savings = annual_transport_savings / 12
            current_monthly_transport_cost = current_monthly_orders * constants.TRANSPORT_COST
            
            monthly_savings_percent = (monthly_transport_savings / current_monthly_transport_cost) * 100 if current_monthly_transport_cost > 0 else 0
            annual_savings_percent = (annual_transport_savings / annual_transport_cost) * 100 if annual_transport_cost > 0 else 0
            implementation_cost = constants.IMPLEMENTATION_COST
            roi_percentage = (annual_transport_savings / implementation_cost) * 100 if implementation_cost > 0 else float('inf')

            savings_cols = st.columns(5)
            with savings_cols[0]:
                st.metric("Monthly Savings", f"KSh {monthly_transport_savings:,.0f}")
            with savings_cols[1]:
                st.metric("Annual Savings", f"KSh {annual_transport_savings:,.0f}")
            with savings_cols[2]:
                st.metric("Monthly Savings %", f"{monthly_savings_percent:.1f}%")
            with savings_cols[3]:
                st.metric("Annual Savings %", f"{annual_savings_percent:.1f}%")
            with savings_cols[4]:
                st.metric("ROI", f"{roi_percentage:.0f}%")

            # ----------------------------------
            # 5. Key Insights & Recommendations
            # ----------------------------------
            st.markdown("#### 📋 Key Insights & Recommendations")
            st.markdown(f"""
            - **EOQ Implementation**: Save KSh {annual_transport_savings:,.0f} annually on transport costs.
            - **Order Frequency**: Reduce from {current_monthly_orders:.1f} to {eoq_monthly_orders:.1f} orders/month.
            - **Payback Period**: {payback_period:.1f} months to recover implementation costs.
            - **Largest Cost**: Product cost ({(annual_product_cost/total_annual_spending)*100:.1f}% of total).
            - **Loss Prevention**: Sublimation losses cost KSh {annual_sublimation_loss:,.0f} annually.
            """)
        else:
            st.warning("🧮 Cost analysis requires historical order data.")
            st.info("Please add the first order for this period using the 'Record Receipt' button in the sidebar to see the cost breakdown.")

    with tab5:
        st.markdown("### 📋 Strategic Recommendations")

        # Immediate actions
        st.markdown("#### 🎯 Recommended Actions")

        recommendations = [
        f"**Implement optimized ordering quantity:** Order {eoq:.0f} kg per shipment (accounts for {avg_sublimation*100:.2f}% sublimation losses)",
        f"**Maintain safety stock:** Keep minimum inventory of {safety_stock:.0f} kg to buffer against demand variability and sublimation",
        f"**Set reorder point:** Initiate new orders when inventory reaches {reorder_point:.0f} kg",
        f"**Optimize order frequency:** Target {eoq_monthly_orders:.1f} orders per month based on demand patterns"
]

        for recommendation in recommendations:
         st.markdown(f"- {recommendation}", unsafe_allow_html=True)
        for i, rec in enumerate(recommendations, 1):
         st.markdown(f"{i}. {rec}")

        # Medium-term improvements
        st.markdown("#### 🔄 Medium-term Improvements")

        medium_term = [
            "**Demand forecasting:** Implement automated forecasting for better demand planning",
            "**Supplier negotiations:** Leverage consistent ordering patterns for better transport rates",
            "**Container optimization:** Standardize orders to maximize container utilization",
            "**Inventory tracking:** Implement real-time inventory monitoring system"
        ]

        for i, rec in enumerate(medium_term, 1):
            st.markdown(f"{i}. {rec}")

        # Key metrics to monitor (now matching the Current vs EOQ Comparison calculations)
        st.markdown("#### 📊 Key Metrics to Monitor")

        avg_order_size = kpis.get('avg_order_size', 0)
        current_monthly_volume = kpis.get('current_monthly_volume', 0)

        if avg_order_size > 0:
            current_inventory_turnover = f"{current_monthly_volume / (avg_order_size/2):.1f}x/month"
        else:
            current_inventory_turnover = "N/A"

        if eoq > 0:
            target_inventory_turnover = f"{current_monthly_volume / eoq:.1f}x/month"
        else:
            target_inventory_turnover = "N/A"

        metrics_to_track = pd.DataFrame({
            'Metric': [
                'Service Level',
                'Inventory Turnover',
                'Stockout Frequency',
                'Order Frequency',
                'Container Utilization',
                'Total Transport Cost'
            ],
            'Current Value': [
                f"{constants.SERVICE_LEVEL*100:.0f}%",
                current_inventory_turnover,  # <-- FIXED LINE
                "Monitor",
                f"{current_monthly_orders:.1f}/month",
                f"{kpis.get('container_utilization', 0)*100:.1f}%",
                f"KSh {current_monthly_orders * constants.TRANSPORT_COST:,.0f}/month"
            ],
            'Target Value': [
                f"{constants.SERVICE_LEVEL*100:.0f}%",
                target_inventory_turnover,  # <-- ALSO FIXED
                "<5%",
                f"{eoq_monthly_orders:.1f}/month",
                ">85%",
                f"KSh {eoq_monthly_orders * constants.TRANSPORT_COST:,.0f}/month"
            ]
        })

        st.dataframe(metrics_to_track, use_container_width=True)

        # Implementation timeline
        st.markdown("#### 📅 Implementation Timeline")

        timeline_data = pd.DataFrame({
            'Week': ['Week 1-2', 'Week 3-4', 'Month 2', 'Month 3', 'Ongoing'],
            'Activities': [
                'Calculate EOQ and safety stock, Set reorder points',
                'Implement new ordering policy, Train staff',
                'Monitor performance, Adjust parameters',
                'Evaluate results, Optimize further',
                'Regular review and adjustment'
            ],
            'Expected Outcome': [
                'Clear inventory targets established',
                'New system operational',
                'Initial cost savings realized',
                'Full optimization achieved',
                'Continuous improvement'
            ]
        })

        st.dataframe(timeline_data, use_container_width=True)

        st.markdown("#### 🌍 Long-term Improvements")
        st.markdown("""
        1. **Supply Chain Diversification**
        - Develop relationships with multiple dry ice suppliers
        - Establish backup transportation routes

        2. **Sustainability Initiatives**
        - Implement CO₂ capture system from fermentation processes
        - Explore renewable energy-powered production

        3. **Automated Replenishment System**
        - IoT sensors with real-time inventory tracking
        - AI-driven predictive ordering

        4. **Carbon Credit Program**
        - Monetize emission reductions from optimized logistics
        - Achieve carbon-neutral certification by 2027
        """)

        # Key metrics dashboard
        st.subheader("📊 Performance Targets")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Supplier Risk Reduction", "40%", "15% achieved")
        with col2:
            st.metric("Stockout Reduction", "30%", "8% improvement")
        with col3:
            st.metric("Carbon Footprint", "-15%", "-5% YoY")
        with col4:
            st.metric("Automation Level", "95%", "25% current")

        # Interactive Plotly timeline
        st.subheader("⏱️ Implementation Timeline")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=['Q3 2025', 'Q4 2025', 'Q1 2026', 'Q2 2026+'],
            y=[1, 2, 3, 4],
            mode='markers+lines+text',
            marker=dict(size=16, color='#3498db'),
            line=dict(color='#2c3e50', width=4),
            text=['Supplier Program', 'IoT Pilot', 'CO₂ Study', 'Full Rollout'],
            textposition='top center',
            name='Milestones'
        ))
        fig.update_layout(
            height=350,
            showlegend=False,
            yaxis=dict(showticklabels=False, title=None),
            xaxis=dict(title='Implementation Quarters'),
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True)

        # Roadmap dataframe with original content
        roadmap_data = {
            'Timeline': ['Q3 2025', 'Q4 2025', 'Q1 2026', 'Q2 2026+'],
            'Initiative': [
                'Supplier diversification program',
                'IoT sensor pilot in 2 facilities',
                'CO₂ capture feasibility study',
                'Full automation rollout'
            ],
            'Target': [
                'Reduce supplier risk by 40%',
                'Cut stockouts by 30%',
                'Decrease carbon footprint by 15%',
                'Achieve 95% automated ordering'
            ]
        }

        roadmap = pd.DataFrame(roadmap_data)

        # Styled dataframe with highlighting
        st.dataframe(
            roadmap.style.applymap(lambda x: 'font-weight: bold', subset=['Timeline'])
                .set_properties(**{'background-color': '#f8f9fa', 'color': '#212529'})
                .highlight_max(axis=0, color='#d4edda'),
            use_container_width=True,
            height=200
        )

        # Expandable implementation details
        with st.expander("🔍 Detailed Implementation Plans", expanded=False):
            selected_quarter = st.selectbox(
                "Select Quarter",
                roadmap['Timeline'].tolist(),
                key='quarter_selector'
            )
            filtered_info = roadmap[roadmap['Timeline'] == selected_quarter]

            st.subheader(f"{selected_quarter} Implementation Plan")
            st.markdown(f"**Initiative:** {filtered_info['Initiative'].values[0]}")
            st.markdown(f"**Target:** {filtered_info['Target'].values[0]}")

            # Quarter-specific details
            if selected_quarter == 'Q3 2025':
                st.markdown("""
                - Identify 3 new dry ice suppliers
                - Negotiate backup transportation contracts
                - Develop risk assessment framework
                """)
                st.progress(30)
            elif selected_quarter == 'Q4 2025':
                st.markdown("""
                - Install IoT sensors in Midwest facilities
                - Develop predictive ordering algorithms
                - Train operations team on new system
                """)
                st.progress(15)
            elif selected_quarter == 'Q1 2026':
                st.markdown("""
                - Technical assessment of CO₂ capture systems
                - Calculate ROI for sustainability investments
                - Partner identification for implementation
                """)
                st.progress(5)
            else:
                st.markdown("""
                - System-wide automation deployment
                - Process optimization across all facilities
                - Integration with finance systems
                """)
                st.progress(0)

            st.caption(f"Current status of {selected_quarter} initiatives")


    with tab6:
        st.markdown("###  Predictive Maintenance Dashboard")
        # Container Health Assessment
        st.markdown("####  Container Health Assessment")

        # Container data
        containers_data = {
            'CTN-001': {'insulation_efficiency': 75, 'seal_integrity': 65, 'structural_condition': 85, 'usage_cycles': 42, 'location': 'Storage Unit #1'},
            'CTN-002': {'insulation_efficiency': 88, 'seal_integrity': 92, 'structural_condition': 90, 'usage_cycles': 28, 'location': 'Storage Unit #2'},
            'CTN-003': {'insulation_efficiency': 60, 'seal_integrity': 55, 'structural_condition': 70, 'usage_cycles': 67, 'location': 'Transport Container #A'}
        }

        # Container selection
        selected_container = st.selectbox(
            "Select Container for Analysis",
            list(containers_data.keys()),
            format_func=lambda x: f"{x} - {containers_data[x]['location']}",
            key="maintenance_container_select" # Added key to avoid widget duplication errors
        )
        container_data = containers_data[selected_container]

        # Calculate health metrics
        health_score = (container_data['insulation_efficiency'] + container_data['seal_integrity'] + container_data['structural_condition']) / 3
        failure_risk = "High" if health_score < 70 else "Medium" if health_score < 85 else "Low"

        # Display health metrics
        health_cols = st.columns(5)
        metrics = [
            ("Insulation Efficiency", f"{container_data['insulation_efficiency']}%"),
            ("Seal Integrity", f"{container_data['seal_integrity']}%"),
            ("Structural Condition", f"{container_data['structural_condition']}%"),
            ("Usage Cycles", container_data['usage_cycles']),
            ("Health Score", f"{health_score:.1f}%")
        ]

        for col, (label, value) in zip(health_cols, metrics):
            with col:
                st.metric(label, value)

        # Risk assessment
        st.markdown("#### 📊 Risk Assessment")
        risk_color = "🔴" if failure_risk == "High" else "🟡" if failure_risk == "Medium" else "🟢"
        st.metric("Failure Risk Level", f"{risk_color} {failure_risk}")

        # Maintenance recommendations
        st.markdown("####  Maintenance Recommendations")
        recommendations = []
        if container_data['insulation_efficiency'] < 70:
            recommendations.append(" Schedule insulation inspection")
        if container_data['seal_integrity'] < 70:
            recommendations.append(" Replace door seals and gaskets")
        if container_data['structural_condition'] < 80:
            recommendations.append(" Conduct structural assessment")
        if container_data['usage_cycles'] > 50:
            recommendations.append("📋 Consider container rotation")
        if not recommendations:
            recommendations.append("✅ Continue regular maintenance")

        for i, action in enumerate(recommendations, 1):
            st.markdown(f"{i}. {action}")

        # System overview
        st.markdown("---")
        st.markdown("####  System Overview")

        overview_cols = st.columns(4)
        overview_metrics = [
            ("Equipment Uptime", "98.2%", "0.5%"),
            ("Temperature Stability", "±0.5°C", "-0.2°C"),
            ("Last Maintenance", "12 days ago", None),
            ("Next Service Due", "18 days", None)
        ]

        for col, (label, value, delta) in zip(overview_cols, overview_metrics):
            with col:
                st.metric(label, value, delta=delta)

        # Maintenance schedule
        st.markdown("#### 📅 Maintenance Schedule")
        maintenance_data = pd.DataFrame({
            'Equipment': ['Storage Unit #1', 'Storage Unit #2', 'Container CTN-001', 'Container CTN-002', 'Container CTN-003', 'Monitoring System'],
            'Last Service': ['2024-06-15', '2024-06-10', '2024-06-05', '2024-06-01', '2024-05-28', '2024-06-20'],
            'Next Service': ['2024-07-15', '2024-07-10', '2024-06-25', '2024-07-01', '2024-06-28', '2024-07-20'],
            'Status': ['Good', 'Good', 'Fair', 'Good', 'Needs Attention', 'Excellent'],
            'Priority': ['Medium', 'Medium', 'High', 'Low', 'High', 'Low']
        })

        maintenance_data['Last Service'] = pd.to_datetime(maintenance_data['Last Service'])
        maintenance_data['Next Service'] = pd.to_datetime(maintenance_data['Next Service'])
        maintenance_data['Days Overdue'] = (pd.Timestamp.today().normalize() - maintenance_data['Next Service']).dt.days

        def style_status(val):
            colors = {'Needs Attention': 'background-color: #fff3cd', 'Excellent': 'background-color: #d4edda',
                     'Good': 'background-color: #d1ecf1', 'Fair': 'background-color: #f8d7da'}
            return colors.get(val, '')

        def style_priority(val):
            colors = {'High': 'background-color: #f8d7da', 'Medium': 'background-color: #fff3cd', 'Low': 'background-color: #d4edda'}
            return colors.get(val, '')

        st.dataframe(
            maintenance_data.style
            .applymap(style_status, subset=['Status'])
            .applymap(style_priority, subset=['Priority'])
            .format({
                'Last Service': lambda x: x.strftime('%Y-%m-%d'),
                'Next Service': lambda x: x.strftime('%Y-%m-%d'),
                'Days Overdue': lambda x: f"{x} days" if x > 0 else "On schedule"
            }),
            use_container_width=True
        )

        overdue_items = maintenance_data[maintenance_data['Days Overdue'] > 0]
        if not overdue_items.empty:
            st.markdown("#### ⚠️ Maintenance Alerts")
            for _, item in overdue_items.iterrows():
                st.error(f" **{item['Equipment']}** is {item['Days Overdue']} days overdue!")

        # Cost tracking
        st.markdown("#### 💰 Maintenance Costs")
        cost_data = pd.DataFrame({
            'Month': pd.date_range('2024-01-01', periods=6, freq='M'),
            'Preventive': [2500, 3200, 2800, 4100, 2900, 3500],
            'Reactive': [1200, 800, 2100, 600, 1800, 900],
            'Emergency': [0, 0, 1500, 0, 0, 2200]
        })

        fig_cost = px.bar(
            cost_data.melt(id_vars=['Month'], var_name='Type', value_name='Cost'),
            x='Month', y='Cost', color='Type',
            title="Monthly Maintenance Costs (KSh)",
            color_discrete_map={'Preventive': '#28a745', 'Reactive': '#ffc107', 'Emergency': '#dc3545'}
        )
        st.plotly_chart(fig_cost, use_container_width=True)

        # ROI calculator
        st.markdown("#### 📈 Maintenance ROI")
        roi_cols = st.columns(3)
        with roi_cols[0]:
            preventive_cost = st.number_input("Annual Preventive Cost (KSh)", value=40000, step=5000)
        with roi_cols[1]:
            avoided_cost = st.number_input("Avoided Reactive Cost (KSh)", value=75000, step=5000)
        with roi_cols[2]:
            downtime_cost = st.number_input("Avoided Downtime Cost (KSh)", value=150000, step=10000)

        total_savings = avoided_cost + downtime_cost
        roi = ((total_savings - preventive_cost) / preventive_cost) * 100 if preventive_cost > 0 else 0

        st.metric("Maintenance ROI", f"{roi:.1f}%")
        if roi > 0:
            st.success(f"💡 Every KSh 1 spent on preventive maintenance saves KSh {total_savings/preventive_cost:.2f} in other costs.")
        else:
            st.warning("⚠️ Consider optimizing maintenance strategy.")

    with tab7:
        st.markdown("## 📜 Inventory Transaction History")

        # --- SECTION 1: PERIOD-SPECIFIC TRANSACTION HISTORY ---
        if not st.session_state.transactions:
            st.info("No transactions recorded for this period yet. Use the sidebar to record usage or receipts.")
        else:
            trans_df = pd.DataFrame(st.session_state.transactions)
            trans_df['date'] = pd.to_datetime(trans_df['date'])
            trans_df = trans_df.sort_values('date', ascending=False)
            
            st.markdown("### 🔍 Filter Transactions")
            filter_col1, filter_col2, filter_col3 = st.columns(3)
            with filter_col1:
                transaction_type = st.selectbox("Transaction Type", ["All", "usage", "receipt"], key="trans_type_filter")
            with filter_col2:
                date_min = trans_df['date'].min().date()
                date_max = trans_df['date'].max().date()
                selected_dates = st.date_input("Date Range", [date_min, date_max], min_value=date_min, max_value=date_max, key="date_range_filter")
            with filter_col3:
                show_limit = st.selectbox("Show Last", ["All", "10", "25", "50", "100"], key="show_limit_filter")
            
            filtered_df = trans_df.copy()
            if transaction_type != "All":
                filtered_df = filtered_df[filtered_df['type'] == transaction_type]
            if len(selected_dates) == 2:
                start_date, end_date = selected_dates
                filtered_df = filtered_df[(filtered_df['date'].dt.date >= start_date) & (filtered_df['date'].dt.date <= end_date)]
            if show_limit != "All":
                filtered_df = filtered_df.head(int(show_limit))

            st.markdown("### 📋 Transaction Records")
            display_df = filtered_df.copy()
            display_df['Date'] = display_df['date'].dt.strftime('%Y-%m-%d %H:%M')
            display_df['Type'] = display_df['type'].str.title()
            display_df['Quantity (kg)'] = display_df['quantity'].apply(lambda x: f"{x:,.2f}")
            st.dataframe(display_df[['Date', 'Type', 'Quantity (kg)', 'description']], use_container_width=True,)
            
            st.markdown("### 📈 Transaction Summary (Filtered Period)")
            total_used = filtered_df[filtered_df['type']=='usage']['quantity'].sum()
            total_received = filtered_df[filtered_df['type']=='receipt']['quantity'].sum()
            net_change = total_received - total_used

            stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
            stat_col1.metric("Total Used", f"{total_used:,.1f} kg")
            stat_col2.metric("Total Received", f"{total_received:,.1f} kg")
            stat_col3.metric("Net Change", f"{net_change:,.1f} kg", delta=f"{net_change:,.1f} kg")
            stat_col4.metric("Total Transactions", len(filtered_df))

            # --- NEW: EXPORT DATA SECTION ---
            st.markdown("### 📥 Export Filtered Data")
            if not filtered_df.empty:
                csv = filtered_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label="Download as CSV",
                   data=csv,
                   file_name=f"transaction_history_{st.session_state.selected_period.replace('/', '-')}_{datetime.now().strftime('%Y%m%d')}.csv",
                   mime='text/csv',
                )
            else:
                st.caption("No data in the current filter to export.")


        # --- DIVIDER TO SEPARATE SECTIONS ---
        st.divider()

        # --- SECTION 2: GLOBAL STATUS & HELP ---
        st.markdown("### 📊 Current Status")
        
        st.metric("Current Stock Level", f"{inventory_tracker.current_stock:,.1f} kg")

        with st.expander("ℹ️ How to Use This Page"):
            st.markdown("""
            1.  **Record Usage:** Use the sidebar to log daily consumption.
            2.  **Record Receipt:** Use the sidebar when new stock arrives.
            3.  **View Transactions:** All transactions will appear here automatically.
            4.  **Filter Data:** Use the filters above to narrow down results.
            5.  **Export Data:** Download buttons appear when transaction data exists.
            """)

        # --- SECTION 3: DATA MANAGEMENT ---
        st.divider()
        st.markdown("### ⚠️ Data Management")
        st.warning("This action will permanently delete ALL transaction and order data for ALL periods. Use with caution.")
        
        if 'confirm_clear_pressed' not in st.session_state:
            st.session_state.confirm_clear_pressed = False

        if st.button("Clear All Transactions and Orders", type="secondary"):
            st.session_state.confirm_clear_pressed = True

        if st.session_state.confirm_clear_pressed:
            st.error("Are you sure? This cannot be undone.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("CONFIRM PERMANENT DELETION", type="primary"):
                    clear_transactions_from_db()
                    st.session_state.transactions = []
                    st.session_state.confirm_clear_pressed = False
                    st.success("All transaction and order data has been permanently cleared!")
                    st.rerun()
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_clear_pressed = False
                    st.rerun()

if __name__ == "__main__":
    main()
