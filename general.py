import logging
import os
import io
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pdf2image import convert_from_path
from google.cloud import vision
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Replace with your actual values
BOT_TOKEN = "YOUR_BOT_TOKEN"  # Replace with your bot's token
PROJECT_ID = "YOUR_PROJECT_ID" # Your Google Cloud Project ID
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "path/to/your/credentials.json" # Path to your service account key file

# Initialize Google Cloud Vision client
client = vision.ImageAnnotatorClient()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message."""
    user = update.effective_user
    await update.response.send_message(
        f"Hi {user.first_name}!\nSend me a PDF file and I will convert it to a searchable PDF using Google Lens.",
        reply_markup=ForceReply(selective=True),
    )

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles PDF file uploads."""
    try:
        # Download the PDF file
        pdf_file = await update.message.document.get_file()
        pdf_bytes = await pdf_file.download_as_bytearray()
        pdf_stream = io.BytesIO(pdf_bytes)

        # Convert PDF pages to images
        images = convert_from_path(pdf_stream, fmt='jpeg')  # Use JPEG for better OCR

        all_text = []

        for i, image in enumerate(images):
            # Convert PIL Image to bytes for Google Cloud Vision
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG')
            image_bytes = img_byte_arr.getvalue()

            # Perform OCR using Google Cloud Vision
            image = vision.Image(content=image_bytes)
            response = client.text_detection(image=image)
            texts = response.text_annotations

            page_text = ""
            if texts:
                page_text = texts[0].description
            all_text.append(page_text)
            logger.info(f"Processed page {i+1}/{len(images)}")
            await update.message.reply_text(f"Processed page {i+1}/{len(images)}")

        # Create a new PDF with the extracted text
        output_pdf_bytes = io.BytesIO()
        pdf_canvas = canvas.Canvas(output_pdf_bytes, pagesize=letter)

        for text in all_text:
            pdf_canvas.drawString(10, 750, text) # Basic text placement. Improve as needed
            pdf_canvas.showPage()
        pdf_canvas.save()

        # Send the new PDF back to the user
        await update.message.reply_document(
            document=output_pdf_bytes.getvalue(), filename="output.pdf"
        )
        logger.info("Finished processing the PDF.")
        await update.message.reply_text("Finished processing the PDF.")

    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        await update.message.reply_text(f"An error occurred: {e}")


def main() -> None:
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))

    application.run_polling()


if __name__ == "__main__":
    main()
