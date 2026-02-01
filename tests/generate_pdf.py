from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def create_test_pdf(filename):
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, height - 100, "TransMax Test Document")
    
    # Subtitle
    c.setFont("Helvetica-Oblique", 14)
    c.drawString(100, height - 130, "Confidential - For Interpretation Only")
    
    # Body Text
    c.setFont("Helvetica", 12)
    text = "This is a sample paragraph for text extraction testing. " * 3
    c.drawString(100, height - 160, text)
    
    c.drawString(100, height - 180, "Another paragraph starts here. It should be detected as a separate block.")
    
    c.save()
    print(f"Created {filename}")

if __name__ == "__main__":
    create_test_pdf("test_sample.pdf")
