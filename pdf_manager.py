# PDF Manager - Handle PDF generation, preview, and document operations

import os
import datetime
import traceback
import AppKit
import Quartz.PDFKit as PDFKit
import drawBot as db
from settings import (
    normalize_path,
    ensure_directory_exists,
    format_timestamp,
    make_safe_filename,
    log_error,
    get_file_size_formatted,
)
from ui import setup_page_format
from proof import reset_proof_page_counter


class PDFManager:
    """Manages PDF generation, preview, and document operations."""

    def __init__(self, settings):
        self.settings = settings
        self.current_pdf_path = None
        self.preview_components = self.create_preview_components()

    def create_preview_components(self):
        """Create PDF preview components for integration into UI."""
        components = {}

        # Create PDFView for preview
        pdfView = PDFKit.PDFView.alloc().initWithFrame_(((0, 0), (100, 100)))
        pdfView.setAutoresizingMask_(1 << 1 | 1 << 4)
        pdfView.setAutoScales_(True)
        pdfView.setDisplaysPageBreaks_(True)
        pdfView.setDisplayMode_(1)
        pdfView.setDisplayBox_(0)

        components["pdfView"] = pdfView
        return components

    def get_pdf_output_directory(self, font_manager):
        """Determine the appropriate PDF output directory."""
        try:
            if font_manager.fonts:
                first_font_path = normalize_path(font_manager.fonts[0])
                family_name = os.path.splitext(os.path.basename(first_font_path))[
                    0
                ].split("-")[0]

                # Check if user wants to use custom PDF output location
                # Ensure pdf_output key exists with defaults
                if "pdf_output" not in self.settings.data:
                    self.settings.data["pdf_output"] = {
                        "use_custom_location": False,
                        "custom_location": "",
                    }

                use_custom = self.settings.data["pdf_output"].get(
                    "use_custom_location", False
                )
                custom_location = self.settings.data["pdf_output"].get(
                    "custom_location", ""
                )

                if use_custom and custom_location and os.path.exists(custom_location):
                    # Use custom location
                    pdf_directory = normalize_path(custom_location)
                else:
                    # Use default: first font's directory
                    pdf_directory = os.path.dirname(first_font_path)

                return pdf_directory, family_name
            else:
                # Fallback to script directory if no fonts loaded
                from core_config import SCRIPT_DIR

                return normalize_path(SCRIPT_DIR), "proof"

        except Exception as e:
            error_msg = f"Error determining PDF output directory: {e}"
            log_error(error_msg)
            from core_config import SCRIPT_DIR

            return normalize_path(SCRIPT_DIR), "proof"

    def generate_pdf_filename(self, family_name, now=None):
        """Generate a unique PDF filename with timestamp."""
        if now is None:
            now = datetime.datetime.now()
        timestamp = format_timestamp(now)
        safe_name = make_safe_filename(f"{timestamp}_{family_name}-proof", ".pdf")
        return safe_name

    def save_pdf_document(self, font_manager, now=None):
        """Save the current drawBot document as a PDF."""
        try:
            pdf_directory, family_name = self.get_pdf_output_directory(font_manager)
            pdf_filename = self.generate_pdf_filename(family_name, now)
            pdf_path = os.path.join(pdf_directory, pdf_filename)

            # Ensure output directory exists
            ensure_directory_exists(pdf_directory)

            # Save the PDF using drawBot
            db.saveImage(pdf_path)
            self.current_pdf_path = pdf_path

            # Log with file size
            file_size = get_file_size_formatted(pdf_path)
            print(f"Proof PDF was saved: {pdf_path} ({file_size})")
            return pdf_path

        except Exception as e:
            error_msg = f"Error saving PDF: {e}"
            log_error(error_msg, traceback.format_exc())
            return None

    def display_pdf(self, pdf_path=None):
        """Display a PDF in the preview component."""
        if pdf_path is None:
            pdf_path = self.current_pdf_path

        if pdf_path and os.path.exists(pdf_path):
            try:
                pdfDoc = PDFKit.PDFDocument.alloc().initWithURL_(
                    AppKit.NSURL.fileURLWithPath_(pdf_path)
                )
                self.preview_components["pdfView"].setDocument_(pdfDoc)
                return True
            except Exception as e:
                print(f"Error displaying PDF: {e}")
                return False
        return False

    def get_preview_view(self):
        """Get the PDF preview view for integration into UI."""
        return self.preview_components["pdfView"]

    def clear_preview(self):
        """Clear the current PDF preview."""
        try:
            self.preview_components["pdfView"].setDocument_(None)
        except Exception as e:
            print(f"Error clearing PDF preview: {e}")

    def open_pdf_in_external_viewer(self, pdf_path=None):
        """Open the PDF in an external application."""
        if pdf_path is None:
            pdf_path = self.current_pdf_path

        if pdf_path and os.path.exists(pdf_path):
            try:
                # Use NSWorkspace to open the PDF
                workspace = AppKit.NSWorkspace.sharedWorkspace()
                workspace.openFile_(pdf_path)
                return True
            except Exception as e:
                print(f"Error opening PDF externally: {e}")
                return False
        return False

    def get_pdf_info(self, pdf_path=None):
        """Get information about the current PDF document."""
        if pdf_path is None:
            pdf_path = self.current_pdf_path

        if pdf_path and os.path.exists(pdf_path):
            try:
                pdfDoc = PDFKit.PDFDocument.alloc().initWithURL_(
                    AppKit.NSURL.fileURLWithPath_(pdf_path)
                )
                if pdfDoc:
                    page_count = pdfDoc.pageCount()
                    file_size = os.path.getsize(pdf_path)
                    return {
                        "path": pdf_path,
                        "page_count": page_count,
                        "file_size": file_size,
                        "filename": os.path.basename(pdf_path),
                    }
            except Exception as e:
                print(f"Error getting PDF info: {e}")
        return None

    def export_pdf_pages(self, output_directory, page_range=None, pdf_path=None):
        """Export specific pages from the PDF as separate files."""
        if pdf_path is None:
            pdf_path = self.current_pdf_path

        if not pdf_path or not os.path.exists(pdf_path):
            return False

        try:
            pdfDoc = PDFKit.PDFDocument.alloc().initWithURL_(
                AppKit.NSURL.fileURLWithPath_(pdf_path)
            )
            if not pdfDoc:
                return False

            total_pages = pdfDoc.pageCount()
            if page_range is None:
                page_range = range(total_pages)

            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            exported_files = []

            for page_index in page_range:
                if 0 <= page_index < total_pages:
                    page = pdfDoc.pageAtIndex_(page_index)
                    if page:
                        # Create a new document with just this page
                        new_doc = PDFKit.PDFDocument.alloc().init()
                        new_doc.insertPage_atIndex_(page, 0)

                        # Save the single page
                        output_filename = make_safe_filename(
                            f"{base_name}_page_{page_index + 1}", ".pdf"
                        )
                        output_path = os.path.join(output_directory, output_filename)
                        new_doc.writeToFile_(output_path)
                        exported_files.append(output_path)

            print(f"Exported {len(exported_files)} pages to {output_directory}")
            return exported_files

        except Exception as e:
            error_msg = f"Error exporting PDF pages: {e}"
            log_error(error_msg, traceback.format_exc())
            return False

    def setup_page_format(self):
        """Set up the page format for PDF generation based on user settings."""
        try:
            # Use utility function for page format setup
            page_format = self.settings.get_page_format()
            setup_page_format(page_format)
        except Exception as e:
            log_error(f"Error setting page format: {e}")

    def begin_pdf_generation(self):
        """Initialize a new PDF document for generation."""
        try:
            self.setup_page_format()
            reset_proof_page_counter()  # Reset page counter for new proof
            db.newDrawing()
            return True
        except Exception as e:
            log_error(f"Error beginning PDF generation: {e}")
            return False

    def end_pdf_generation(self, font_manager, now=None):
        """Finalize PDF generation and save the document."""
        try:
            db.endDrawing()
            return self.save_pdf_document(font_manager, now)
        except Exception as e:
            log_error(f"Error ending PDF generation: {e}")
            return None

    def get_current_pdf_path(self):
        """Get the path of the currently generated PDF."""
        return self.current_pdf_path

    def set_current_pdf_path(self, path):
        """Set the path of the current PDF."""
        self.current_pdf_path = path
