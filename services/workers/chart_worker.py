from pathlib import Path
from datetime import datetime
import json


class ChartWorker:
    """Generate chart artifacts (HTML with embedded chart data)."""
    
    def __init__(self, output_dir: str = "data/artifacts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, chart_data: dict, title: str = "Chart") -> str:
        """Generate HTML chart from data."""
        
        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.html"
        filepath = self.output_dir / filename
        
        # Simple HTML template with Chart.js
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: system-ui; padding: 20px; }}
        #chart {{ max-width: 800px; margin: 0 auto; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div id="chart">
        <canvas id="myChart"></canvas>
    </div>
    <script>
        const ctx = document.getElementById('myChart');
        const chartData = {json.dumps(chart_data)};
        new Chart(ctx, chartData);
    </script>
</body>
</html>"""
        
        filepath.write_text(html, encoding='utf-8')
        
        return str(filepath)
