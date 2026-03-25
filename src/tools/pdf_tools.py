"""PDF processing tools."""
from typing import Optional, Dict, List
import io
from pathlib import Path

from src.utils.logger import logger
from src.utils.http_pool import http_pool
import aiohttp


async def extract_text_from_pdf(file_path: str, max_pages: int = 10) -> Dict:
    """Extract text from PDF file.
    
    Args:
        file_path: Path to PDF file
        max_pages: Maximum number of pages to extract (default: 10)
        
    Returns:
        Dictionary with extracted text and metadata
    """
    try:
        # Try to import PyPDF2 or pdfplumber
        try:
            import PyPDF2
            use_pypdf2 = True
        except ImportError:
            try:
                import pdfplumber
                use_pypdf2 = False
            except ImportError:
                return {
                    "error": "PDF library not installed. Install PyPDF2 or pdfplumber: pip install PyPDF2 pdfplumber",
                    "suggestion": "Run: pip install PyPDF2 pdfplumber"
                }
        
        if not Path(file_path).exists():
            return {"error": f"File not found: {file_path}"}
        
        text_content = []
        metadata = {}
        
        with open(file_path, 'rb') as file:
            if use_pypdf2:
                pdf_reader = PyPDF2.PdfReader(file)
                metadata = {
                    "num_pages": len(pdf_reader.pages),
                    "title": pdf_reader.metadata.get("/Title", "") if pdf_reader.metadata else "",
                    "author": pdf_reader.metadata.get("/Author", "") if pdf_reader.metadata else "",
                }
                
                pages_to_extract = min(max_pages, len(pdf_reader.pages))
                for i in range(pages_to_extract):
                    page = pdf_reader.pages[i]
                    text_content.append({
                        "page": i + 1,
                        "text": page.extract_text()
                    })
            else:
                with pdfplumber.open(file) as pdf:
                    metadata = {
                        "num_pages": len(pdf.pages),
                        "title": pdf.metadata.get("Title", "") if pdf.metadata else "",
                        "author": pdf.metadata.get("Author", "") if pdf.metadata else "",
                    }
                    
                    pages_to_extract = min(max_pages, len(pdf.pages))
                    for i in range(pages_to_extract):
                        page = pdf.pages[i]
                        text_content.append({
                            "page": i + 1,
                            "text": page.extract_text() or ""
                        })
        
        return {
            "success": True,
            "metadata": metadata,
            "pages_extracted": len(text_content),
            "text": "\n\n".join([f"Page {p['page']}:\n{p['text']}" for p in text_content]),
            "full_text": " ".join([p['text'] for p in text_content]),
        }
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return {"error": f"Error extracting PDF text: {str(e)}"}


async def extract_text_from_pdf_url(url: str, max_pages: int = 10) -> Dict:
    """Extract text from PDF URL.
    
    Args:
        url: URL to PDF file
        max_pages: Maximum number of pages to extract
        
    Returns:
        Dictionary with extracted text and metadata
    """
    try:
        async with http_pool.get_session() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return {"error": f"Failed to download PDF: HTTP {response.status}"}
                
                # Download PDF to memory
                pdf_data = await response.read()
                
                # Try to import PDF library
                try:
                    import PyPDF2
                    use_pypdf2 = True
                except ImportError:
                    try:
                        import pdfplumber
                        use_pypdf2 = False
                    except ImportError:
                        return {
                            "error": "PDF library not installed",
                            "suggestion": "Run: pip install PyPDF2 pdfplumber"
                        }
                
                text_content = []
                metadata = {}
                
                pdf_file = io.BytesIO(pdf_data)
                
                if use_pypdf2:
                    pdf_reader = PyPDF2.PdfReader(pdf_file)
                    metadata = {
                        "num_pages": len(pdf_reader.pages),
                        "title": pdf_reader.metadata.get("/Title", "") if pdf_reader.metadata else "",
                    }
                    
                    pages_to_extract = min(max_pages, len(pdf_reader.pages))
                    for i in range(pages_to_extract):
                        page = pdf_reader.pages[i]
                        text_content.append({
                            "page": i + 1,
                            "text": page.extract_text()
                        })
                else:
                    with pdfplumber.open(pdf_file) as pdf:
                        metadata = {
                            "num_pages": len(pdf.pages),
                            "title": pdf.metadata.get("Title", "") if pdf.metadata else "",
                        }
                        
                        pages_to_extract = min(max_pages, len(pdf.pages))
                        for i in range(pages_to_extract):
                            page = pdf.pages[i]
                            text_content.append({
                                "page": i + 1,
                                "text": page.extract_text() or ""
                            })
                
                return {
                    "success": True,
                    "url": url,
                    "metadata": metadata,
                    "pages_extracted": len(text_content),
                    "text": "\n\n".join([f"Page {p['page']}:\n{p['text']}" for p in text_content]),
                    "full_text": " ".join([p['text'] for p in text_content]),
                }
                
    except Exception as e:
        logger.error(f"Error extracting text from PDF URL: {e}")
        return {"error": f"Error processing PDF from URL: {str(e)}"}


async def get_pdf_info(file_path: str) -> Dict:
    """Get PDF file information.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        PDF metadata dictionary
    """
    try:
        try:
            import PyPDF2
        except ImportError:
            try:
                import pdfplumber
            except ImportError:
                return {"error": "PDF library not installed"}
        
        if not Path(file_path).exists():
            return {"error": f"File not found: {file_path}"}
        
        with open(file_path, 'rb') as file:
            try:
                import PyPDF2
                pdf_reader = PyPDF2.PdfReader(file)
                return {
                    "num_pages": len(pdf_reader.pages),
                    "metadata": dict(pdf_reader.metadata) if pdf_reader.metadata else {},
                    "encrypted": pdf_reader.is_encrypted,
                }
            except:
                import pdfplumber
                with pdfplumber.open(file) as pdf:
                    return {
                        "num_pages": len(pdf.pages),
                        "metadata": pdf.metadata or {},
                    }
                    
    except Exception as e:
        logger.error(f"Error getting PDF info: {e}")
        return {"error": str(e)}

