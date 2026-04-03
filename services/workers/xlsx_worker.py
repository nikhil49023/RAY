from pathlib import Path
from datetime import datetime
import csv


class XLSXWorker:
    """Generate XLSX/CSV artifacts."""
    
    def __init__(self, output_dir: str = "data/artifacts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, data: list, title: str = "Data", format: str = "csv") -> str:
        """Generate spreadsheet from structured data."""
        
        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.{format}"
        filepath = self.output_dir / filename
        
        # Write CSV (simple implementation)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            if data and len(data) > 0:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        
        return str(filepath)
