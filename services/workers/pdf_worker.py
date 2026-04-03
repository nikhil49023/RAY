from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime


class PDFWorker:
    """Generate PDF artifacts."""
    
    def __init__(self, output_dir: str = "data/artifacts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate(self, content: str, title: str = "Document") -> str:
        """Generate PDF from text content."""
        
        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.pdf"
        filepath = self.output_dir / filename
        
        # Create PDF
        doc = SimpleDocTemplate(str(filepath), pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        story.append(Paragraph(title, styles['Title']))
        story.append(Spacer(1, 12))
        
        # Content
        for paragraph in content.split('\n\n'):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), styles['BodyText']))
                story.append(Spacer(1, 6))
        
        doc.build(story)
        
        return str(filepath)
