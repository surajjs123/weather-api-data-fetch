import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
import base64
import os
import tempfile
import warnings
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
import openpyxl

app = Flask(__name__)

# Database setup
def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect('weather_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            temperature_2m REAL,
            relative_humidity_2m REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def insert_weather_data(data, lat, lon):
    """Insert weather data into database"""
    conn = sqlite3.connect('weather_data.db')
    cursor = conn.cursor()
    
    timestamps = data['hourly']['time']
    temperatures = data['hourly']['temperature_2m']
    humidity = data['hourly']['relative_humidity_2m']
    
    for i in range(len(timestamps)):
        cursor.execute('''
            INSERT OR REPLACE INTO weather_data 
            (timestamp, latitude, longitude, temperature_2m, relative_humidity_2m)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamps[i], lat, lon, temperatures[i], humidity[i]))
    
    conn.commit()
    conn.close()

def get_weather_data_from_db(hours=48):
    """Retrieve weather data from database for the last N hours"""
    conn = sqlite3.connect('weather_data.db')
   
    cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
    now_time = datetime.now().isoformat()
    
    # Query to get data within the time range
    query = '''
        SELECT timestamp, temperature_2m, relative_humidity_2m, latitude, longitude
        FROM weather_data 
        WHERE timestamp >= ? AND timestamp <= ?
        ORDER BY timestamp ASC
    '''
    
    df = pd.read_sql_query(query, conn, params=(cutoff_time, now_time))
    

    print(f"Querying for data between {cutoff_time} and {now_time}")
    print(f"Retrieved {len(df)} records")
    if not df.empty:
        print(f"Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    conn.close()
    return df

# Enhanced debugging function
def debug_weather_data():
    """Debug function to check what's in the database"""
    conn = sqlite3.connect('weather_data.db')
    cursor = conn.cursor()
    
    # Check total records
    cursor.execute('SELECT COUNT(*) FROM weather_data')
    total_records = cursor.fetchone()[0]
    
    # Check date range
    cursor.execute('SELECT MIN(timestamp), MAX(timestamp) FROM weather_data')
    date_range = cursor.fetchone()
    
    # Check recent records
    cursor.execute('SELECT timestamp, temperature_2m FROM weather_data ORDER BY timestamp DESC LIMIT 10')
    recent_records = cursor.fetchall()
    
    conn.close()
    
    print(f"Total records: {total_records}")
    print(f"Date range: {date_range[0]} to {date_range[1]}")
    print("Recent records:")
    for record in recent_records:
        print(f"  {record[0]}: {record[1]}°C")
    
    return {
        'total_records': total_records,
        'date_range': date_range,
        'recent_records': recent_records
    }

def create_chart_base64(df):
    """Create matplotlib chart and return as base64 encoded string"""
    # Create the chart
    plt.style.use('default')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    
    # Temperature plot
    ax1.plot(df['timestamp'], df['temperature_2m'], 'r-', linewidth=2, label='Temperature')
    ax1.set_ylabel('Temperature (°C)', fontsize=12)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_title(f'Temperature and Humidity Over Time (Last {len(df)} Hours)', fontsize=14, fontweight='bold')
    
    # Humidity plot
    ax2.plot(df['timestamp'], df['relative_humidity_2m'], 'b-', linewidth=2, label='Humidity')
    ax2.set_ylabel('Relative Humidity (%)', fontsize=12)
    ax2.set_xlabel('Time', fontsize=12)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Format x-axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
    
    plt.tight_layout()
    
    # Convert to base64
    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
    img_buffer.seek(0)
    img_base64 = base64.b64encode(img_buffer.read()).decode()
    plt.close()
    
    return img_base64

def generate_html_report(df, chart_base64, hours=48):
    """Generate HTML report for PDF conversion"""
    # Get location info
    lat = df['latitude'].iloc[0] if not df.empty else 'N/A'
    lon = df['longitude'].iloc[0] if not df.empty else 'N/A'
    
    # Calculate statistics
    avg_temp = df['temperature_2m'].mean()
    min_temp = df['temperature_2m'].min()
    max_temp = df['temperature_2m'].max()
    avg_humidity = df['relative_humidity_2m'].mean()
    
    # Create data table rows
    table_rows = ""
    for _, row in df.head(10).iterrows():  # Show first 10 records in table
        table_rows += f"""
        <tr>
            <td>{pd.to_datetime(row['timestamp']).strftime('%Y-%m-%d %H:%M')}</td>
            <td>{row['temperature_2m']:.1f}°C</td>
            <td>{row['relative_humidity_2m']:.1f}%</td>
        </tr>
        """
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Weather Data Report</title>
        <style>
            @page {{
                size: A4;
                margin: 2cm;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 3px solid #2c5282;
                padding-bottom: 20px;
            }}
            
            .header h1 {{
                color: #2c5282;
                font-size: 28px;
                margin: 0;
                font-weight: bold;
            }}
            
            .header h2 {{
                color: #4a5568;
                font-size: 18px;
                margin: 10px 0 0 0;
                font-weight: normal;
            }}
            
            .metadata {{
                background-color: #f7fafc;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
            }}
            
            .metadata-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
            }}
            
            .metadata-item {{
                display: flex;
                justify-content: space-between;
                padding: 8px 0;
                border-bottom: 1px solid #e2e8f0;
            }}
            
            .metadata-item:last-child {{
                border-bottom: none;
            }}
            
            .metadata-label {{
                font-weight: bold;
                color: #2d3748;
            }}
            
            .metadata-value {{
                color: #4a5568;
            }}
            
            .statistics {{
                background-color: #edf2f7;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
            }}
            
            .statistics h3 {{
                color: #2c5282;
                margin-top: 0;
                margin-bottom: 15px;
            }}
            
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
            }}
            
            .stat-box {{
                background: white;
                border-radius: 6px;
                padding: 15px;
                text-align: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            
            .stat-value {{
                font-size: 24px;
                font-weight: bold;
                color: #2c5282;
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                color: #718096;
                font-size: 14px;
            }}
            
            .chart-container {{
                text-align: center;
                margin: 30px 0;
                page-break-inside: avoid;
            }}
            
            .chart-container img {{
                max-width: 100%;
                height: auto;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .data-table {{
                margin-top: 30px;
                page-break-inside: avoid;
            }}
            
            .data-table h3 {{
                color: #2c5282;
                margin-bottom: 15px;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            
            th {{
                background-color: #2c5282;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: bold;
            }}
            
            td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e2e8f0;
            }}
            
            tr:nth-child(even) {{
                background-color: #f7fafc;
            }}
            
            .footer {{
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #e2e8f0;
                text-align: center;
                color: #718096;
                font-size: 12px;
            }}
            
            .page-break {{
                page-break-before: always;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Weather Data Report</h1>
            <h2>Temperature and Humidity Analysis</h2>
        </div>
        
        <div class="metadata">
            <div class="metadata-grid">
                <div>
                    <div class="metadata-item">
                        <span class="metadata-label">Location:</span>
                        <span class="metadata-value">Lat {lat}°, Lon {lon}°</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Data Points:</span>
                        <span class="metadata-value">{len(df)} records</span>
                    </div>
                </div>
                <div>
                    <div class="metadata-item">
                        <span class="metadata-label">Date Range:</span>
                        <span class="metadata-value">{df['timestamp'].min().strftime('%Y-%m-%d %H:%M')} to {df['timestamp'].max().strftime('%Y-%m-%d %H:%M')}</span>
                    </div>
                    <div class="metadata-item">
                        <span class="metadata-label">Generated:</span>
                        <span class="metadata-value">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="statistics">
            <h3>Statistical Summary</h3>
            <div class="stats-grid">
                <div class="stat-box">
                    <div class="stat-value">{avg_temp:.1f}°C</div>
                    <div class="stat-label">Average Temperature</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{avg_humidity:.1f}%</div>
                    <div class="stat-label">Average Humidity</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{min_temp:.1f}°C / {max_temp:.1f}°C</div>
                    <div class="stat-label">Min / Max Temperature</div>
                </div>
                <div class="stat-box">
                    <div class="stat-value">{(max_temp - min_temp):.1f}°C</div>
                    <div class="stat-label">Temperature Range</div>
                </div>
            </div>
        </div>
        
        <div class="chart-container">
            <img src="data:image/png;base64,{chart_base64}" alt="Weather Chart">
        </div>
        
        <div class="data-table page-break">
            <h3>Recent Data Sample (First 10 Records)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Temperature</th>
                        <th>Humidity</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p><strong>Data Source:</strong> Open-Meteo MeteoSwiss API</p>
            <p><strong>Generated by:</strong> Weather Data Backend Service</p>
            <p><strong>Report Type:</strong> {hours}-Hour Weather Analysis</p>
        </div>
    </body>
    </html>
    """
    
    return html_content

@app.route('/weather-report', methods=['GET'])
def fetch_weather_report():
    """Fetch weather data from Open-Meteo API and store in database"""
    try:
        # Get parameters from query string
        lat = request.args.get('lat', default=47.37, type=float)
        lon = request.args.get('lon', default=8.55, type=float)
        
        # Prepare API request
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': lat,
            'longitude': lon,
            'hourly': ['temperature_2m', 'relative_humidity_2m'],
            'past_days': 2
        }
        
        # Make API request
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Store in database
        insert_weather_data(data, lat, lon)
        
        return jsonify({
            'status': 'success',
            'message': 'Weather data fetched and stored successfully',
            'location': {'latitude': lat, 'longitude': lon},
            'data_points': len(data['hourly']['time'])
        })
        
    except requests.RequestException as e:
        return jsonify({'error': f'API request failed: {str(e)}'}), 500
    except Exception as e:
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/export/excel', methods=['GET'])
def export_excel():
    """Export weather data to Excel file"""
    try:
        # Get hours parameter from query string, default to 48
        hours = request.args.get('hours', default=48, type=int)
        
        # Debug: Check what's in the database
        debug_info = debug_weather_data()
        print("Database debug info:", debug_info)
        
        # Get data from database for specified time period
        df = get_weather_data_from_db(hours)
        
        if df.empty:
            return jsonify({
                'error': 'No data available for export',
                'debug_info': debug_info
            }), 404
        
        print(f"Retrieved {len(df)} records from database")
        
        # Prepare Excel file
        excel_buffer = BytesIO()
       
        df_export = df[['timestamp', 'temperature_2m', 'relative_humidity_2m']].copy()
        df_export.columns = ['Timestamp', 'Temperature (°C)', 'Relative Humidity (%)']
        
        # Convert timestamp to datetime for better formatting
        df_export['Timestamp'] = pd.to_datetime(df_export['Timestamp'])
        
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, sheet_name='Weather Data', index=False)
            
            
            workbook = writer.book
            worksheet = writer.sheets['Weather Data']
            
           
            for row in range(2, len(df_export) + 2):
                cell = worksheet[f'A{row}']
                cell.number_format = 'YYYY-MM-DD HH:MM:SS'
        
        excel_buffer.seek(0)
        
        return send_file(
            excel_buffer,
            as_attachment=True,
            download_name=f'weather_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        return jsonify({'error': f'Excel export failed: {str(e)}'}), 500

@app.route('/export/pdf', methods=['GET'])
def export_pdf():
    """Generate PDF report using WeasyPrint"""
    try:
        
        hours = request.args.get('hours', default=48, type=int)

        df = get_weather_data_from_db(hours)
        
        if df.empty:
            return jsonify({'error': 'No data available for export'}), 404
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')
        
        # Create chart as base64
        chart_base64 = create_chart_base64(df)
        
        # Generate HTML content
        html_content = generate_html_report(df, chart_base64, hours)
        
        # Convert HTML to PDF using WeasyPrint with suppressed font warnings
        pdf_buffer = BytesIO()
        
        import sys
        import io
        from contextlib import redirect_stderr
    
        font_config = FontConfiguration()
        
        # Generate PDF with error suppression
        with redirect_stderr(io.StringIO()):
            try:
                HTML(string=html_content).write_pdf(
                    pdf_buffer,
                    font_config=font_config,
                    presentational_hints=True
                )
            except Exception:
                # Ultimate fallback - basic PDF generation
                HTML(string=html_content).write_pdf(pdf_buffer)
        
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f'weather_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'error': f'PDF export failed: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'weather-data-backend'
    })

@app.route('/', methods=['GET'])
def index():
    """API documentation endpoint"""
    return jsonify({
        'service': 'Weather Data Backend API',
        'endpoints': {
            'GET /weather-report?lat={lat}&lon={lon}': 'Fetch and store weather data',
            'GET /export/excel': 'Export weather data as Excel file',
            'GET /export/pdf': 'Generate PDF report with chart',
            'GET /health': 'Health check',
            'GET /': 'API documentation'
        }
    })

def get_all_weather_data_from_db():
    """Retrieve ALL weather data from database for debugging"""
    conn = sqlite3.connect('weather_data.db')
    
    query = '''
        SELECT timestamp, temperature_2m, relative_humidity_2m, latitude, longitude, created_at
        FROM weather_data 
        ORDER BY timestamp DESC
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@app.route('/debug/data', methods=['GET'])
def debug_data():
    """Debug endpoint to check database contents"""
    try:
        debug_info = debug_weather_data()
        df = get_all_weather_data_from_db()
        
        return jsonify({
            'database_info': debug_info,
            'sample_data': df.head(10).to_dict('records') if not df.empty else [],
            'total_records_returned': len(df)
        })
    except Exception as e:
        return jsonify({'error': f'Debug failed: {str(e)}'}), 500

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # Run the Flask app

    app.run(debug=True, host='0.0.0.0', port=5000)
